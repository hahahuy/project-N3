"""FastAPI application factory for the local Real2Scenario browser demo."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import threading
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from real2scenario import state_to_dict

from .adapter import ArtifactAdapter, ArtifactRecord
from .build_info import build_identity
from .config import WebSettings
from .jobs import BatchService, PreviewService, to_results
from .esmini import EsminiBackend, ReplayJob
from .schemas import (
    BatchRequest,
    BatchResults,
    JobStatus,
    ScenarioDetail,
    ScenarioSummary,
    SettingsUpdateRequest,
    SettingsView,
    SourceSceneImportRequest,
    SourceSceneImportResponse,
    TrajectoryResponse,
    VariantResult,
    ExportResponse,
    ReplayRequest,
    ReplayJobView,
    PreviewRequest,
    PreviewResponse,
    CP1ReviewView,
    CP1ReviewItem,
    WorkspaceDocumentView,
    ScenarioViewPayload,
    AvailabilityView,
    ActorPoseView,
    ScenarioLayerView,
    MetricAvailabilityView,
    TrajectoryState,
    SimulatorCapabilityView,
    POVFrameView,
    POVImageFrameView,
    ActorTimelineView,
    GateTimelineView,
    RecipeDocumentView,
    RecipeStepRequest,
    RecipeStepStateRequest,
    StepMoveRequest,
    RollbackMarkerRequest,
    VariantLineageView,
    EvidenceLayersView,
    CompareView,
    VariantSensorStatusView,
    LiveSessionCreateRequest,
    LiveSessionCommandRequest,
    LiveScenarioPairRequest,
    WasmScenarioPairView,
    ArtifactLink,
    CanvasBranchRequest,
    CanvasBranchResponse,
    TestingPhysicsResponse,
    ValidationView,
    ValidationReasonView,
)
from .actor_timeline import actor_timeline
from .compare import compare_payload
from .evidence_layers import evidence_layers
from .gate_timeline import gate_timeline
from .lineage import variant_lineage
from .recipe import RecipeStore
from .source_scenes import SourceSceneAdapter, resolve_scene_map_name
from .sensor_status import variant_sensor_status
from .native_map import NativeMapService
from .ground import GROUND_CONTRACT_VERSION, GroundService
from .lidar import LidarService
from .camera import CameraEvidenceService
from .preview_time import resolve_preview_time
from .nuscenes_adapter import NuScenesDatasetAdapter
from .frames import capability as frame_capability, frame as render_frame, _state_at as _state_at_preview
from .live_session import LiveSessionService
from real2scenario import (
    MAP_BUILDER_VERSION,
    STRAIGHT_ROAD_TOPOLOGY,
    OpenDriveTemplate,
    RoadAlignedTransform,
    Scenario,
    State,
    atomic_write_bytes,
    build_opendrive_from_nuscenes,
    select_full_scene_map,
    select_opendrive_template,
    transform_opendrive_to_local,
    write_openscenario,
    CanvasKeyframe,
    VariantConfig,
    build_canvas_keyframe_branch,
    variant_artifact_to_dict,
    validate_feasibility,
)

from pathlib import Path
from fastapi.responses import Response

WASM_PAIR_EXPORTER_VERSION = "openscenario-exporter-v5"

_TEMPLATE_MAP_WARNING = "OpenDRIVE output uses a local template approximation; it is not lossless map conversion."
_FULLMAP_MAP_WARNING = "OpenDRIVE is a full nuScenes map reconstruction in the scenario local frame (line-segment approximation); lane-level details differ from the recorded map."


def _scenario_map_name(scenario: Scenario, settings: WebSettings) -> str | None:
    """Resolve a scenario's map name without extracting any geometry.

    ``include_map=false`` skips the full-map build, which would otherwise leave
    the response without a map name even though resolving it is cheap.
    """
    scene_token = scenario.provenance.get("source_scene_token")
    if not scene_token:
        return None
    try:
        return resolve_scene_map_name(scene_token, settings)
    except (KeyError, OSError, ValueError):
        return None


def _preview_etag(payload: object) -> str:
    """Stable validator for a static preview payload.

    Derived from the canonical JSON encoding, so the tag changes if and only if
    the geometry changes. Display-only: this is a cache validator, not provenance.
    """
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )
    return f'"{digest.hexdigest()[:32]}"'


def _map_layers_by_name(layers: object) -> dict[str, object]:
    """Normalize map layers to the ``layer name -> polygons`` mapping.

    Two shapes reach here. ``GroundService.layers`` already returns
    ``{"name", "polygons"}`` records whose polygons carry ``exterior``/``holes``,
    which is what the preview draws. ``GroundService.full_layers`` keys layers
    by name instead and records geometry as ``{"token", "geometry": [ring, ...]}``,
    so its records are rewritten into the same ``exterior`` form; without that the
    preview silently drew no map at all.
    """
    if isinstance(layers, list):
        return {
            str(layer["name"]): layer.get("polygons", [])
            for layer in layers
            if isinstance(layer, dict) and "name" in layer
        }
    if not isinstance(layers, dict):
        return {}
    normalized: dict[str, object] = {}
    for name, records in layers.items():
        if not isinstance(records, list):
            normalized[str(name)] = records
            continue
        polygons = []
        for record in records:
            if not isinstance(record, dict):
                continue
            if "exterior" in record:
                polygons.append(record)
                continue
            rings = record.get("geometry")
            if isinstance(rings, list) and rings and isinstance(rings[0], list):
                # Emit only what the preview draws. Keeping the raw `geometry`
                # alongside would ship every coordinate ring twice, which grew
                # the static map payload from 1.4MB to 3.3MB.
                polygons.append({"token": record.get("token"), "exterior": rings[0], "holes": rings[1:]})
        normalized[str(name)] = polygons
    return normalized


def _fullmap_wasm_pair(
    record: ArtifactRecord, settings: WebSettings
) -> tuple[Scenario, OpenDriveTemplate, Path, str]:
    """Build a wasm-pair with the scene's own full map instead of the template.

    Returns (selected scenario, template, pair root, map warning). Raises
    (KeyError, OSError, RuntimeError, ValueError) on any failure so the caller
    falls back to the template path — a missing map must never break preview.
    """
    provenance = record.scenario.provenance
    scene_token = provenance["source_scene_token"]
    transform = RoadAlignedTransform.from_provenance(provenance)
    map_name = resolve_scene_map_name(scene_token, settings)
    cached = settings.output_root / "maps" / f"{map_name}.xodr"
    if cached.is_file():
        global_text = cached.read_text(encoding="utf-8")
    else:
        manifest = build_opendrive_from_nuscenes(
            settings.dataset_root, map_name=map_name, output_path=cached
        )
        if manifest.get("road_count", 0) == 0:
            raise ValueError(f"Full-map build for {map_name!r} produced no roads.")
        global_text = cached.read_text(encoding="utf-8")
    local_text = transform_opendrive_to_local(global_text, transform)
    road_filename = f"{map_name}.xodr"
    pair_key = hashlib.sha256(
        f"wasm:{WASM_PAIR_EXPORTER_VERSION}:fullmap:{map_name}:{record.scenario.scenario_id}".encode("utf-8")
    ).hexdigest()[:24]
    pair_root = settings.output_root / "wasm-pairs" / pair_key
    pair_root.mkdir(parents=True, exist_ok=True)
    xodr_path = pair_root / road_filename
    # Atomic: concurrent regeneration POSTs (dev StrictMode double-mount,
    # double tabs) must never expose a half-written road to artifact GETs.
    atomic_write_bytes(xodr_path, local_text.encode("utf-8"))
    selected, template = select_full_scene_map(
        record.scenario,
        map_name=map_name,
        road_filename=road_filename,
        map_builder_version=str(MAP_BUILDER_VERSION),
        staged_path=xodr_path,
    )
    return selected, template, pair_root, _FULLMAP_MAP_WARNING


def create_app(settings: WebSettings | None = None) -> FastAPI:
    resolved_settings = settings or WebSettings.from_environment()
    testing_physics_lock = threading.Lock()
    wasm_pair_lock = threading.Lock()
    adapter = ArtifactAdapter(resolved_settings)
    source_scenes = SourceSceneAdapter(resolved_settings)
    native_maps = NativeMapService(resolved_settings)
    ground = GroundService(resolved_settings)
    lidar = LidarService(resolved_settings)
    camera = CameraEvidenceService(resolve_preview_time)
    recipes = RecipeStore()
    batches = BatchService(resolved_settings, adapter)
    previews = PreviewService(resolved_settings, adapter)
    esmini = EsminiBackend(resolved_settings, adapter)
    live_sessions = LiveSessionService(resolved_settings.project_root, resolved_settings.esmini_lib)
    app = FastAPI(title="Real2Scenario Local Demo", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.adapter = adapter
    app.state.batches = batches
    app.state.previews = previews
    app.state.source_scenes = source_scenes
    app.state.native_maps = native_maps
    app.state.ground = ground
    app.state.lidar = lidar
    app.state.camera = camera
    app.state.recipes = recipes
    app.state.esmini = esmini
    app.state.live_sessions = live_sessions
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    def record_for(scenario_id: str):
        """Resolve one artifact or fail with the API-owned message."""
        try:
            return adapter.get(scenario_id)
        except (KeyError, FileNotFoundError, ImportError, OSError, RuntimeError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    def layers_for(record) -> dict[str, object]:
        """Evidence layers for one artifact, derived from its own files."""
        replay_path = record.path.with_name(f"{record.path.stem}.replay.json")
        return evidence_layers(
            record.scenario,
            artifact_type=record.artifact_type,
            replay_trace_available=replay_path.is_file(),
            replay_artifact=adapter.relative_path(replay_path) if replay_path.is_file() else None,
            lidar=lidar,
            settings=resolved_settings,
            parent_scenario_id=record.parent_scenario_id,
        )

    def metric_availability(record) -> MetricAvailabilityView:
        """Replay metric availability with provenance and scientific status."""
        trajectory = adapter.trajectory(record)
        metrics = trajectory.replay_metrics
        return MetricAvailabilityView(
            available=bool(metrics),
            unavailable_reason=None if metrics else "replay_trace_not_available",
            source="replay_trace" if metrics else "none",
            alignment_method=(
                next(iter(metrics.values())).alignment_method if metrics else None
            ),
            scientific_status="PROVISIONAL",
            provenance={
                key: record.scenario.provenance[key]
                for key in ("dataset_version", "source_scene_token", "coordinate_transform_version")
                if key in record.scenario.provenance
            },
            per_actor=metrics,
        )

    @app.get("/api/health")
    def health() -> dict[str, object]:
        dataset_root = resolved_settings.dataset_root
        dataset_path = (
            None
            if dataset_root is None
            else dataset_root / resolved_settings.dataset_version
        )
        return {
            "status": "ok",
            "build": build_identity(),
            "artifact_root_configured": resolved_settings.artifact_root.is_dir(),
            "scenario_count": len(adapter.discover()),
            "dataset_configured": dataset_path is not None,
            "dataset_version": resolved_settings.dataset_version,
            "dataset_metadata_available": bool(dataset_path and dataset_path.is_dir()),
            # Which stack answered, and which roots it is actually reading.
            # Several stacks can run on one host with different artifact roots,
            # so "the catalog looks empty" is otherwise indistinguishable from
            # "this api serves a different directory". Every root is reported
            # with its real path and whether it exists on disk.
            "configuration": {
                "project_root": resolved_settings.project_root.as_posix(),
                "artifact_root": resolved_settings.artifact_root.as_posix(),
                "output_root": resolved_settings.output_root.as_posix(),
                "dataset_root": None if dataset_root is None else dataset_root.as_posix(),
                "roots_present": {
                    "project_root": resolved_settings.project_root.is_dir(),
                    "artifact_root": resolved_settings.artifact_root.is_dir(),
                    "output_root": resolved_settings.output_root.is_dir(),
                    "dataset_root": None if dataset_root is None else dataset_root.is_dir(),
                },
            },
        }

    @app.get("/api/settings", response_model=SettingsView)
    def get_settings() -> SettingsView:
        return _settings_view(resolved_settings, source_scenes)

    @app.get("/api/esmini")
    def esmini_capability() -> dict[str, object]:
        return esmini.capability()

    @app.get("/api/esmini/live/capability")
    def esmini_live_capability() -> dict[str, object]:
        return live_sessions.capability()

    @app.post("/api/esmini/live/sessions")
    def create_live_session(request: LiveSessionCreateRequest) -> dict[str, object]:
        try:
            session = live_sessions.create(
                request.scenario_id, request.xosc_path, request.xodr_path, request.timestep_s
            )
            return session.metadata()
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/esmini/live/scenario-pairs")
    def create_live_scenario_pair(request: LiveScenarioPairRequest) -> dict[str, object]:
        """Materialize a private XOSC/XODR pair and create its native session."""
        try:
            record = adapter.get(request.scenario_id)
            selected, template = select_opendrive_template(
                record.scenario, topology=STRAIGHT_ROAD_TOPOLOGY
            )
            pair_key = hashlib.sha256(request.scenario_id.encode("utf-8")).hexdigest()[:24]
            pair_root = resolved_settings.output_root / "live-pairs" / pair_key
            pair_root.mkdir(parents=True, exist_ok=True)
            xosc = write_openscenario(selected, template, pair_root / "scenario.xosc")
            xodr = pair_root / Path(template.relative_path).name
            atomic_write_bytes(xodr, template.path().read_bytes())
            session = live_sessions.create(request.scenario_id, str(xosc), str(xodr), request.timestep_s)
            return session.metadata() | {
                "artifacts": {
                    "openscenario": f"/api/artifacts/{xosc.relative_to(resolved_settings.project_root).as_posix()}",
                    "opendrive": f"/api/artifacts/{xodr.relative_to(resolved_settings.project_root).as_posix()}",
                }
            }
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (OSError, RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/workspace/scenarios/{scenario_id}/wasm-pair", response_model=WasmScenarioPairView)
    def create_wasm_scenario_pair(scenario_id: str) -> WasmScenarioPairView:
        """Materialize a private XOSC/XODR pair for browser WASM preview only."""
        if not wasm_pair_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="wasm_pair_busy_retry")
        try:
            record = adapter.get(scenario_id)
            try:
                selected, template, pair_root, map_warning = _fullmap_wasm_pair(
                    record, resolved_settings
                )
            except (KeyError, OSError, RuntimeError, ValueError):
                selected, template = select_opendrive_template(
                    record.scenario, topology=STRAIGHT_ROAD_TOPOLOGY
                )
                pair_key = hashlib.sha256(f"wasm:{WASM_PAIR_EXPORTER_VERSION}:{scenario_id}".encode("utf-8")).hexdigest()[:24]
                pair_root = resolved_settings.output_root / "wasm-pairs" / pair_key
                pair_root.mkdir(parents=True, exist_ok=True)
                map_warning = _TEMPLATE_MAP_WARNING
            xosc = write_openscenario(selected, template, pair_root / "scenario.xosc")
            xodr = pair_root / Path(template.relative_path).name
            atomic_write_bytes(xodr, template.path().read_bytes())
            return WasmScenarioPairView(
                scenario_id=scenario_id,
                coordinate_frame=selected.coordinate_frame,
                map_warning=map_warning,
                openscenario=f"/api/artifacts/{xosc.relative_to(resolved_settings.project_root).as_posix()}",
                opendrive=f"/api/artifacts/{xodr.relative_to(resolved_settings.project_root).as_posix()}",
                artifact_visibility="local_private",
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (OSError, RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        finally:
            wasm_pair_lock.release()

    @app.get("/api/esmini/live/sessions/{session_id}")
    def get_live_session(session_id: str) -> dict[str, object]:
        try:
            return live_sessions.get(session_id).frame()
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/api/esmini/live/sessions/{session_id}/commands")
    def command_live_session(session_id: str, request: LiveSessionCommandRequest) -> dict[str, object]:
        try:
            return live_sessions.get(session_id).command(request.command, request.payload)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.delete("/api/esmini/live/sessions/{session_id}")
    def close_live_session(session_id: str) -> dict[str, object]:
        try:
            live_sessions.close(session_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"session_id": session_id, "status": "closed"}

    @app.websocket("/api/esmini/live/sessions/{session_id}/stream")
    async def stream_live_session(websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        try:
            session = live_sessions.get(session_id)
            await websocket.send_json(session.frame())
            while True:
                message = await websocket.receive_json()
                command = LiveSessionCommandRequest.model_validate(message)
                payload = session.command(command.command, command.payload)
                await websocket.send_json(payload)
        except (KeyError, ValueError, RuntimeError) as error:
            await websocket.send_json({"contract_version": "esmini-live-session-v1", "message_type": "error", "error": str(error)})
        except WebSocketDisconnect:
            return

    @app.get("/api/cp1/review", response_model=CP1ReviewView)
    def cp1_review() -> CP1ReviewView:
        return CP1ReviewView(
            review_version="cp1-owner-review-v1",
            diagnostic_status="diagnostic",
            scientific_status="PROVISIONAL",
            scene="scene-0061",
            corridor_baseline={
                "states": 143,
                "matched_states": 20,
                "raw_match_rate": 0.13986,
                "display": "20/143 = 13.99%",
                "all_vehicle_rate": "57.37%",
                "must_remain_unchanged": True,
            },
            scope_note=(
                "Read-only owner checklist. Review evidence and record decisions outside this page; "
                "the page cannot change actor selection, thresholds, lane direction or CP1 status."
            ),
            items=[
                CP1ReviewItem(
                    item_id="baseline",
                    category="baseline",
                    title="Freeze and confirm the immutable baseline",
                    status="ready",
                    blocking=True,
                    what_to_verify="Confirm scene-0061, 40 m corridor, selected actor scope, 143 states and 20 matched states.",
                    owner_action="Confirm the displayed 20/143 baseline is present in every later comparison.",
                    evidence=["docs/current/cp1-manual-review-protocol.md", "docs/reports/cp1-corridor-external-evidence.md"],
                    related_api=["GET /api/cp1/review"],
                ),
                CP1ReviewItem(
                    item_id="sequence-evaluation",
                    category="semantic alignment",
                    title="Run the private lane-sequence evaluation",
                    status="blocked",
                    blocking=True,
                    what_to_verify="Run the new matcher for ego, selected interaction actors and all vehicles.",
                    owner_action="Provide the approved private run with nearest-lane, HMM, high-confidence-only, ambiguity and topology counts.",
                    evidence=["docs/reports/cp1-automated-semantic-alignment-implementation.md", "src/real2scenario/road_match.py"],
                    related_api=["GET /api/cp1/review"],
                ),
                CP1ReviewItem(
                    item_id="topology",
                    category="lane graph",
                    title="Validate explicit lane topology",
                    status="blocked",
                    blocking=True,
                    what_to_verify="Check predecessor, successor, legal lane-change and connector links, including endpoint and heading compatibility.",
                    owner_action="Confirm topology provenance from the map builder; record unresolved links as geometry/topology failures.",
                    evidence=["src/real2scenario/road_match.py", "docs/current/cp1-automated-semantic-alignment.md"],
                    related_api=["GET /api/cp1/review"],
                ),
                CP1ReviewItem(
                    item_id="direction",
                    category="direction",
                    title="Review heading and direction conflicts",
                    status="blocked",
                    blocking=True,
                    what_to_verify="Compare annotation yaw, motion heading, forward lane heading and reverse counterfactual results.",
                    owner_action="Classify conflicts without reversing production lanes for individual actors.",
                    evidence=["docs/reports/cp1-corridor-direction-footprint-analysis.md", "docs/current/cp1-manual-review-protocol.md"],
                    related_api=["GET /api/cp1/review"],
                ),
                CP1ReviewItem(
                    item_id="geometry",
                    category="geometry",
                    title="Separate map geometry failures from track failures",
                    status="blocked",
                    blocking=True,
                    what_to_verify="Check finite centerlines, positive lengths, sample spacing, polygon area, widths, linked endpoints and linked headings.",
                    owner_action="Record geometry failures separately; do not use esmini load success as semantic validation.",
                    evidence=["docs/reports/cp1-corridor-external-evidence.md", "src/real2scenario/road_match.py"],
                    related_api=["GET /api/cp1/review"],
                ),
                CP1ReviewItem(
                    item_id="footprint",
                    category="occupancy",
                    title="Review footprint and missing dimensions",
                    status="blocked",
                    blocking=True,
                    what_to_verify="Keep center-point match, polygon containment, annotation dimensions, fallback width and unsupported dimensions separate.",
                    owner_action="Do not guess ego dimensions or turn unsupported occupancy into a lane failure.",
                    evidence=["docs/reports/cp1-corridor-external-evidence.md", "docs/reports/cp1-corridor-direction-footprint-analysis.md"],
                    related_api=["GET /api/cp1/review"],
                ),
                CP1ReviewItem(
                    item_id="manual-intervals",
                    category="owner review",
                    title="Review only intervals routed by the diagnostic",
                    status="ready",
                    blocking=True,
                    what_to_verify="Inspect low-margin, unresolved-topology, high-lateral-residual, heading-conflict and ambiguous intervals.",
                    owner_action="Record each interval as source/track, frame/yaw, direction, lateral association, footprint, unsupported, off-map, geometry or uncertain.",
                    evidence=["docs/current/cp1-manual-review-protocol.md", "docs/reports/cp1-automated-semantic-alignment-implementation.md"],
                    related_api=["GET /api/cp1/review"],
                ),
                CP1ReviewItem(
                    item_id="acceptance",
                    category="scientific boundary",
                    title="Confirm the non-claims before closure",
                    status="informational",
                    blocking=True,
                    what_to_verify="Confirm no CP1 acceptance, G3 completion, final threshold change or production lane-direction change is being claimed.",
                    owner_action="Close the review as diagnostic/provisional only until all approved evidence gates are complete.",
                    evidence=["docs/current/project-status.md", "docs/current/technical-contracts.md"],
                    related_api=["GET /api/cp1/review"],
                ),
            ],
        )

    @app.post("/api/replays", response_model=ReplayJobView, status_code=202)
    def create_replay(request: ReplayRequest) -> ReplayJobView:
        try:
            adapter.get(request.scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _replay_view(esmini.submit(request.scenario_id))

    @app.get("/api/replays/{job_id}", response_model=ReplayJobView)
    def get_replay(job_id: str) -> ReplayJobView:
        try:
            return _replay_view(esmini.get(job_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/api/settings", response_model=SettingsView)
    def update_settings(request: SettingsUpdateRequest) -> SettingsView:
        nonlocal resolved_settings, adapter, source_scenes, batches, previews, esmini, native_maps, lidar, recipes
        try:
            resolved_settings = resolved_settings.with_paths(
                artifact_root=request.artifact_root,
                output_root=request.output_root,
                dataset_root=request.dataset_root,
                dataset_version=request.dataset_version,
            )
            adapter = ArtifactAdapter(resolved_settings)
            source_scenes = SourceSceneAdapter(resolved_settings)
            batches = BatchService(resolved_settings, adapter)
            previews = PreviewService(resolved_settings, adapter)
            esmini = EsminiBackend(resolved_settings, adapter)
            native_maps = NativeMapService(resolved_settings)
            lidar = LidarService(resolved_settings)
            app.state.settings = resolved_settings
            app.state.adapter = adapter
            app.state.source_scenes = source_scenes
            app.state.batches = batches
            app.state.previews = previews
            app.state.esmini = esmini
            app.state.native_maps = native_maps
            app.state.lidar = lidar
            recipes = RecipeStore()
            app.state.recipes = recipes
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _settings_view(resolved_settings, source_scenes)

    @app.get("/api/source-scenes")
    def list_source_scenes():
        try:
            return list(source_scenes.discover())
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/source-scenes/{scene_token}/import", response_model=SourceSceneImportResponse)
    def import_source_scene(
        scene_token: str, request: SourceSceneImportRequest
    ) -> SourceSceneImportResponse:
        try:
            imported = source_scenes.import_scene(
                scene_token,
                start_sample_token=request.start_sample_token,
                end_sample_token=request.end_sample_token,
                max_distance_m=request.max_distance_m,
                max_ttc_s=request.max_ttc_s,
                max_actors=request.max_actors,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return imported

    @app.get("/api/scenarios", response_model=list[ScenarioSummary])
    def list_scenarios() -> list[ScenarioSummary]:
        return [adapter.summary(record) for record in adapter.discover()]

    @app.get("/api/scenarios/{scenario_id}", response_model=ScenarioDetail)
    def get_scenario(scenario_id: str) -> ScenarioDetail:
        try:
            return adapter.detail(adapter.get(scenario_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/workspace/documents/{scenario_id}", response_model=WorkspaceDocumentView)
    def workspace_document(scenario_id: str) -> WorkspaceDocumentView:
        try:
            record = adapter.get(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        scenario = record.scenario
        provenance = dict(scenario.provenance)
        esmini_info = esmini.capability()
        dataset_available = resolved_settings.dataset_root is not None and (
            resolved_settings.dataset_root / resolved_settings.dataset_version
        ).is_dir()
        return WorkspaceDocumentView(
            document_name=scenario.scenario_id,
            branch="main" if record.parent_scenario_id is None else "variant",
            version=provenance.get("generator_version", "canonical-scenario-v1"),
            active_scenario_id=scenario.scenario_id,
            connection=AvailabilityView(available=True, unavailable_reason=None),
            dataset=AvailabilityView(available=dataset_available, unavailable_reason=None if dataset_available else "dataset_not_configured"),
            esmini=AvailabilityView(available=bool(esmini_info["available"]), unavailable_reason=None if esmini_info["available"] else esmini_info["diagnostic"]),
            dataset_version=provenance.get("dataset_version", resolved_settings.dataset_version if dataset_available else None),
            esmini_version=esmini_info.get("version"),
            coordinate_frame=scenario.coordinate_frame,
            transform_version=provenance.get("coordinate_transform_version"),
            provenance=provenance,
            native_map=AvailabilityView(**native_maps.capability(provenance.get("map_name", "singapore-onenorth"))),
            simulator_frames=SimulatorCapabilityView(**frame_capability(scenario)),
        )

    @app.get("/api/workspace/maps/{map_name}/capability")
    def native_map_capability(map_name: str = "singapore-onenorth") -> dict[str, object]:
        return native_maps.capability(map_name)

    @app.get("/api/workspace/maps/{map_name}/patch")
    def native_map_patch_query(
        map_name: str,
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
        layers: str = "road_segment,road_block,stop_line,traffic_light,ped_crossing,walkway,lane_divider,road_divider,drivable_area",
    ) -> dict[str, object]:
        try:
            return native_maps.patch(map_name, (x_min, y_min, x_max, y_max), [item for item in layers.split(",") if item])
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/workspace/maps/{map_name}/road-ahead")
    def native_map_road_ahead(map_name: str, x_m: float, y_m: float) -> dict[str, object]:
        try:
            return native_maps.road_ahead(map_name, x_m, y_m)
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/workspace/lidar/capability")
    def lidar_capability() -> dict[str, object]:
        return lidar.capability()

    @app.get("/api/workspace/lidar/{sample_data_token}")
    def lidar_payload(sample_data_token: str, decimation: int = 8):
        try:
            metadata, payload = lidar.payload(sample_data_token, decimation)
        except (FileNotFoundError, ImportError, KeyError, OSError, RuntimeError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return Response(content=payload, media_type="application/octet-stream", headers={"X-R2S-Lidar-Metadata": json.dumps(metadata, separators=(",", ":"))})

    @app.get("/api/workspace/scenarios/{scenario_id}/lidar")
    def workspace_lidar(scenario_id: str) -> dict[str, object]:
        try:
            record = adapter.get(scenario_id)
            source_window = record.scenario.provenance.get("source_window", "")
            sample_data_token = lidar.sample_data_token(source_window.split(":", 1)[0])
            if not sample_data_token:
                raise ValueError("recorded_lidar_sample_unavailable")
            return {**lidar.descriptor(sample_data_token), "sample_data_token": sample_data_token, "payload_url": f"/api/workspace/lidar/{sample_data_token}"}
        except (KeyError, FileNotFoundError, ImportError, OSError, RuntimeError, ValueError) as error:
            return {"available": False, "unavailable_reason": str(error)}

    @app.get("/api/workspace/scenarios/{scenario_id}/lidar-sweeps")
    def workspace_lidar_sweeps(scenario_id: str) -> dict[str, object]:
        try:
            record = adapter.get(scenario_id)
            source_window = record.scenario.provenance.get("source_window", "")
            first_sample_token, _, last_sample_token = source_window.partition(":")
            if not first_sample_token or not last_sample_token:
                raise ValueError("recorded_lidar_window_unavailable")
            return {
                "contract_version": "nuscenes-lidar-sweeps-v1",
                "channel": "LIDAR_TOP",
                "sweeps": lidar.sweep_window(first_sample_token, last_sample_token),
            }
        except (KeyError, FileNotFoundError, ImportError, OSError, RuntimeError, ValueError) as error:
            return {
                "contract_version": "nuscenes-lidar-sweeps-v1",
                "status": "unavailable",
                "unavailable_reason": str(error),
                "sweeps": [],
            }

    @app.get("/api/workspace/scenarios/{scenario_id}/sensor-evidence")
    def workspace_sensor_evidence(scenario_id: str, nsweeps: int = 5) -> dict[str, object]:
        try:
            record = adapter.get(scenario_id)
            source_window = record.scenario.provenance.get("source_window", "")
            sample_data_token = lidar.sample_data_token(source_window.split(":", 1)[0])
            if not sample_data_token:
                raise ValueError("recorded_lidar_sample_unavailable")
            return lidar.sensor_evidence(sample_data_token, nsweeps)
        except (KeyError, FileNotFoundError, ImportError, OSError, RuntimeError, ValueError) as error:
            return {
                "contract_version": "nuscenes-sensor-evidence-v1",
                "channel": "LIDAR_TOP",
                "status": "unavailable",
                "unavailable_reason": str(error),
                "sweeps": [],
                "artifact_visibility": "local_private",
            }

    @app.get("/api/workspace/scenarios/{scenario_id}/ground-layers")
    def workspace_ground_layers(scenario_id: str) -> dict[str, object]:
        try:
            record = adapter.get(scenario_id)
            return ground.layers(record.scenario)
        except (KeyError, FileNotFoundError, ImportError, OSError, RuntimeError, ValueError) as error:
            return {
                "contract_version": GROUND_CONTRACT_VERSION,
                "status": "unavailable",
                "unavailable_reason": str(error),
                "layers": [],
            }

    @app.get("/api/workspace/scenarios/{scenario_id}/top-down")
    def workspace_top_down(scenario_id: str, source: str = "lidar", nsweeps: int = 5):
        try:
            record = adapter.get(scenario_id)
            sample_data_token = lidar.sample_data_token(record.scenario.provenance.get("source_window", "").split(":", 1)[0])
            if not sample_data_token:
                raise ValueError("recorded_sensor_sample_unavailable")
            return Response(
                content=lidar.topdown(sample_data_token, source=source, nsweeps=nsweeps),
                media_type="image/png",
                headers={"Cache-Control": "private, max-age=60"},
            )
        except (KeyError, FileNotFoundError, ImportError, OSError, RuntimeError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/workspace/scenarios/{scenario_id}/top-down-map")
    def workspace_top_down_map(scenario_id: str, request: Request, response: Response) -> dict[str, object]:
        """Return the scenario's static map geometry, separate from the playhead.

        The geometry depends only on the scenario's map and local transform, so
        it does not change while the playhead moves. Serving it on its own lets
        the browser fetch it once and reuse the response, instead of re-shipping
        roughly 1.7 MB of polygons on every playhead change.
        """
        try:
            record = adapter.get(scenario_id)
            raw = ground.full_layers(record.scenario)
            map_payload = {**raw, "layers": _map_layers_by_name(raw.get("layers"))}
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        etag = _preview_etag(map_payload)
        if request.headers.get("if-none-match") == etag:
            response.status_code = 304
            return {}
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "private, max-age=3600"
        return map_payload

    @app.get("/api/workspace/scenarios/{scenario_id}/top-down-state")
    def workspace_top_down_state(
        scenario_id: str, time_s: float = 0.0, include_map: bool = True
    ) -> dict[str, object]:
        """Return local map geometry plus canonical actor state for preview only.

        ``include_map`` lets a caller that already holds the static geometry
        request only the per-playhead state. It defaults to True so existing
        callers keep the combined payload.
        """
        try:
            record = adapter.get(scenario_id)
            scenario = record.scenario
            if not 0.0 <= time_s <= scenario.duration_s:
                raise ValueError("preview_time_out_of_range")
            map_payload = ground.full_layers(scenario) if include_map else {}
            source_window = scenario.provenance.get("source_window", "")
            first_sample, _, last_sample = source_window.partition(":")
            recorded = NuScenesDatasetAdapter.for_dataset(resolved_settings.dataset_root, resolved_settings.dataset_version).recorded_annotations_window(first_sample, last_sample, time_s)
            transform = RoadAlignedTransform.from_provenance(scenario.provenance)
            try:
                from pyquaternion import Quaternion
                for box in recorded["boxes"]:
                    center = box["center_global"]
                    local = transform.to_local_state(State(time_s=time_s, x_m=center[0], y_m=center[1], yaw_rad=0.0, speed_mps=0.0))
                    box["center_local"] = [local.x_m, local.y_m]
                    box["yaw_local_rad"] = float(Quaternion(box["rotation_wxyz"]).yaw_pitch_roll[0] - transform.heading_rad)
            except (ImportError, KeyError, TypeError, ValueError):
                for box in recorded["boxes"]:
                    box["center_local"] = None
                    box["yaw_local_rad"] = None
            actors = []
            for actor in scenario.actors:
                if not actor.trajectory:
                    continue
                state = _state_at_preview(actor.trajectory, time_s)
                actors.append({
                    "actor_id": actor.actor_id,
                    "actor_type": actor.actor_type,
                    "role": "ego" if actor.actor_id == scenario.ego_actor_id else "actor",
                    "time_s": state.time_s,
                    "x_m": state.x_m,
                    "y_m": state.y_m,
                    "yaw_rad": state.yaw_rad,
                    "speed_mps": state.speed_mps,
                    "dimensions": {"length_m": actor.length_m, "width_m": actor.width_m, "height_m": actor.height_m},
                })
            return {
                "contract_version": "workspace-top-down-state-v1",
                "scenario_id": scenario_id,
                "requested_time_s": time_s,
                "resolved_time_s": time_s,
                "coordinate_frame": scenario.coordinate_frame,
                "map_name": (
                map_payload.get("map_name")
                if include_map
                else _scenario_map_name(scenario, resolved_settings)
            ) or scenario.provenance.get("map_name", "unknown"),
                "map_layers": _map_layers_by_name(map_payload.get("layers")) if include_map else {},
                "actors": actors,
                "recorded_annotations": recorded,
                "provenance": {"map_source": "nuscenes-devkit-NuScenesMap", "actor_source": "recorded_nuscenes_annotations", "artifact_visibility": "local_private"},
            }
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/workspace/scenarios/{scenario_id}/recorded-annotations")
    def workspace_recorded_annotations(scenario_id: str) -> dict[str, object]:
        try:
            record = adapter.get(scenario_id)
            first, _, last = record.scenario.provenance.get("source_window", "").partition(":")
            tracks = NuScenesDatasetAdapter.for_dataset(resolved_settings.dataset_root, resolved_settings.dataset_version).recorded_annotation_tracks(first, last)
            transform = RoadAlignedTransform.from_provenance(record.scenario.provenance)
            for track in tracks:
                for state in track["states"]:
                    center = state["center_global"]
                    local = transform.to_local_state(State(time_s=state["time_s"], x_m=center[0], y_m=center[1], yaw_rad=0.0, speed_mps=0.0))
                    state["center_local"] = [local.x_m, local.y_m]
                    state["yaw_local_rad"] = local.yaw_rad
            return {"contract_version": "workspace-recorded-annotations-v1", "scenario_id": scenario_id, "coordinate_frame": "local_road_aligned", "display_only": True, "native_replay_included": False, "tracks": tracks, "provenance": {"source": "nuscenes-devkit-recorded-annotations", "artifact_visibility": "local_private"}}
        except (KeyError, FileNotFoundError, ImportError, OSError, RuntimeError, ValueError) as error:
            return {"contract_version": "workspace-recorded-annotations-v1", "scenario_id": scenario_id, "display_only": True, "native_replay_included": False, "tracks": [], "status": "unavailable", "unavailable_reason": str(error), "provenance": {"artifact_visibility": "local_private"}}

    @app.get("/api/workspace/scenarios/{scenario_id}/camera-evidence")
    def workspace_camera_evidence(scenario_id: str, channel: str = "CAM_FRONT", time_s: float = 0.0) -> dict[str, object]:
        """Resolve one recorded camera image and its independent overlay layers."""
        try:
            record = adapter.get(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if channel not in {"CAM_FRONT_RIGHT", "CAM_FRONT", "CAM_FRONT_LEFT", "CAM_BACK_RIGHT", "CAM_BACK_LEFT", "CAM_BACK"}:
            raise HTTPException(status_code=422, detail="unsupported_camera_channel")
        try:
            first, _, last = record.scenario.provenance.get("source_window", "").partition(":")
            frame = CameraEvidenceService.from_dataset_window(
                adapter=NuScenesDatasetAdapter.for_dataset(resolved_settings.dataset_root, resolved_settings.dataset_version),
                first_sample_token=first,
                last_sample_token=last,
                channel=channel,
                requested_time_s=time_s,
                canonical_cuboids=[
                    {
                        "actor_id": actor.actor_id,
                        "actor_type": actor.actor_type,
                        "state": {
                            "x_m": _state_at_preview(actor.trajectory, time_s).x_m,
                            "y_m": _state_at_preview(actor.trajectory, time_s).y_m,
                            "yaw_rad": _state_at_preview(actor.trajectory, time_s).yaw_rad,
                        },
                        "size_m": [actor.length_m, actor.width_m, actor.height_m],
                        "visibility": "canonical_scenario",
                    }
                    for actor in record.scenario.actors
                    if actor.trajectory
                ],
            )
            sample_token = str(frame.image.get("sample_data_token") or "")
            return {
                "contract_version": frame.contract_version,
                "scenario_id": scenario_id,
                "channel": frame.channel,
                "requested_time_s": frame.requested_time_s,
                "resolved_time_s": frame.resolved_time_s,
                "timestamp_us": frame.timestamp_us,
                "selection_policy": frame.selection_policy,
                "status": "rendered",
                "image": {**frame.image, "url": f"/api/workspace/camera-image/{sample_token}"},
                "calibration": dict(frame.calibration),
                "recorded_cuboids": list(frame.recorded_cuboids),
                "canonical_cuboids": list(frame.canonical_cuboids),
                "lidar_points": [{"u": point.u, "v": point.v, "depth_m": point.depth_m} for point in frame.lidar_points],
                "provenance": dict(frame.provenance),
            }
        except (FileNotFoundError, ImportError, OSError, RuntimeError, ValueError, KeyError) as error:
            return {"contract_version": "nuscenes-camera-evidence-v1", "scenario_id": scenario_id, "channel": channel, "requested_time_s": time_s, "resolved_time_s": None, "timestamp_us": None, "selection_policy": "nearest", "status": "unavailable", "unavailable_reason": str(error), "image": None, "recorded_cuboids": [], "canonical_cuboids": [], "lidar_points": [], "provenance": {"artifact_visibility": "local_private"}}

    @app.get("/api/workspace/camera-image/{sample_data_token}")
    def workspace_camera_image(sample_data_token: str):
        if resolved_settings.dataset_root is None:
            raise HTTPException(status_code=404, detail="dataset_not_configured")
        try:
            _, path = NuScenesDatasetAdapter.for_dataset(resolved_settings.dataset_root, resolved_settings.dataset_version).camera_file(sample_data_token)
            return FileResponse(path)
        except (FileNotFoundError, ImportError, OSError, RuntimeError, ValueError, KeyError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
    @app.get("/api/workspace/scenarios/{scenario_id}", response_model=ScenarioViewPayload)
    def workspace_scenario(scenario_id: str) -> ScenarioViewPayload:
        try:
            record = adapter.get(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        trajectory = adapter.trajectory(record)
        map_name = record.scenario.provenance.get("map_name", "singapore-onenorth")
        map_payload = None
        map_capability = native_maps.capability(map_name)
        frames = SimulatorCapabilityView(**frame_capability(record.scenario))
        if map_capability["available"]:
            try:
                map_payload = native_maps.layers(map_name)
            except (ImportError, OSError, RuntimeError, ValueError):
                map_payload = None
        actors = [
            ActorPoseView(
                actor_id=actor.actor_id,
                actor_type=actor.actor_type,
                role="ego" if actor.actor_id == record.scenario.ego_actor_id else "actor",
                states=[TrajectoryState(**state_to_dict(state)) for state in actor.trajectory],
                dimensions=AvailabilityView(
                    available=actor.length_m is not None and actor.width_m is not None,
                    unavailable_reason=None if actor.length_m is not None and actor.width_m is not None else "actor_dimensions_unavailable",
                ),
                length_m=actor.length_m,
                width_m=actor.width_m,
                height_m=actor.height_m,
            )
            for actor in record.scenario.actors
        ]
        has_generated = record.artifact_type == "variant"
        return ScenarioViewPayload(
            scenario=adapter.summary(record),
            actors=actors,
            paths=trajectory.paths,
            layers=ScenarioLayerView(
                recorded_path=AvailabilityView(available=not has_generated, unavailable_reason=None if not has_generated else "recorded_path_not_primary_for_variant"),
                generated_path=AvailabilityView(available=has_generated, unavailable_reason=None if has_generated else "generated_path_not_available"),
                map_lanes=AvailabilityView(available=False, unavailable_reason="map_lane_geometry_not_available_in_current_artifact"),
                actor_dimensions=AvailabilityView(
                    available=all(actor.length_m is not None and actor.width_m is not None for actor in record.scenario.actors),
                    unavailable_reason=None if all(actor.length_m is not None and actor.width_m is not None for actor in record.scenario.actors) else "one_or_more_actor_dimensions_unavailable",
                ),
                xodr_geometry=AvailabilityView(available=False, unavailable_reason="xodr_viewer_geometry_not_available"),
                lidar=AvailabilityView(**{key: value for key, value in lidar.capability().items() if key in {"available", "unavailable_reason"}}),
                third_person=frames,
                in_car=frames,
            ),
            metrics=metric_availability(record),
            evidence_layers=EvidenceLayersView(**layers_for(record)),
            sensor_status=VariantSensorStatusView(**variant_sensor_status(record, lidar)),
            native_map=map_payload,
            gates=gate_timeline(record.scenario)["gates"],
            time_s=0.0,
            simulator_frames=frames,
        )

    @app.get("/api/workspace/scenarios/{scenario_id}/timeline", response_model=ActorTimelineView)
    def workspace_timeline(scenario_id: str) -> ActorTimelineView:
        """Time-indexed actor state tracks with explicit channel availability."""
        try:
            record = adapter.get(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return ActorTimelineView(**actor_timeline(record.scenario, resolved_settings))

    @app.get("/api/workspace/scenarios/{scenario_id}/gate-timeline", response_model=GateTimelineView)
    def workspace_gate_timeline(scenario_id: str) -> GateTimelineView:
        """Gate lane segments with backend statuses, reasons and time extents."""
        try:
            record = adapter.get(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return GateTimelineView(**gate_timeline(record.scenario))

    @app.get("/api/workspace/scenarios/{scenario_id}/lineage", response_model=VariantLineageView)
    def workspace_lineage(scenario_id: str) -> VariantLineageView:
        """Parent chain, branch identity, seed and configuration hash."""
        try:
            record = adapter.get(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return VariantLineageView(
            **variant_lineage(record, records=adapter.discover())
        )

    @app.get(
        "/api/workspace/scenarios/{scenario_id}/evidence-layers",
        response_model=EvidenceLayersView,
    )
    def workspace_evidence_layers(scenario_id: str) -> EvidenceLayersView:
        """Recorded, generated, replayed and sensor-evidence layers, separately."""
        try:
            record = adapter.get(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return EvidenceLayersView(**layers_for(record))

    @app.get(
        "/api/workspace/scenarios/{scenario_id}/compare",
        response_model=CompareView,
    )
    def workspace_compare(scenario_id: str, against: str, time_s: float = 0.0) -> CompareView:
        """Synchronized side-by-side comparison against another scenario."""
        if against == scenario_id:
            raise HTTPException(status_code=422, detail="compare_requires_two_different_scenarios")
        try:
            left = adapter.get(scenario_id)
            right = adapter.get(against)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return CompareView(
            **compare_payload(
                left,
                right,
                time_s=time_s,
                left_metrics=metric_availability(left).model_dump(),
                right_metrics=metric_availability(right).model_dump(),
                left_evidence=layers_for(left),
                right_evidence=layers_for(right),
            )
        )

    @app.get(
        "/api/workspace/scenarios/{scenario_id}/recipe",
        response_model=RecipeDocumentView,
    )
    def workspace_recipe(scenario_id: str) -> RecipeDocumentView:
        """Ordered recipe steps, rollback markers and non-destructive history."""
        return RecipeDocumentView(**recipes.view(record_for(scenario_id)))

    @app.post(
        "/api/workspace/scenarios/{scenario_id}/recipe/steps",
        response_model=RecipeDocumentView,
    )
    def workspace_recipe_add_step(
        scenario_id: str, request: RecipeStepRequest
    ) -> RecipeDocumentView:
        record = record_for(scenario_id)
        if any(step.step_id == request.step_id for step in recipes.document(record).current.steps):
            raise HTTPException(status_code=409, detail=f"step_id {request.step_id!r} already exists")
        return RecipeDocumentView(**recipes.add_step(record, request))

    @app.post(
        "/api/workspace/scenarios/{scenario_id}/recipe/steps/{step_id}/active",
        response_model=RecipeDocumentView,
    )
    def workspace_recipe_step_state(
        scenario_id: str, step_id: str, request: RecipeStepStateRequest
    ) -> RecipeDocumentView:
        record = record_for(scenario_id)
        try:
            return RecipeDocumentView(**recipes.set_step_active(record, step_id, request))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/api/workspace/scenarios/{scenario_id}/recipe/steps/{step_id}/remove",
        response_model=RecipeDocumentView,
    )
    def workspace_recipe_remove_step(
        scenario_id: str, step_id: str
    ) -> RecipeDocumentView:
        record = record_for(scenario_id)
        try:
            return RecipeDocumentView(**recipes.remove_step(record, step_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post(
        "/api/workspace/scenarios/{scenario_id}/recipe/steps/move",
        response_model=RecipeDocumentView,
    )
    def workspace_recipe_move_step(
        scenario_id: str, request: StepMoveRequest
    ) -> RecipeDocumentView:
        record = record_for(scenario_id)
        try:
            return RecipeDocumentView(**recipes.move_step(record, request))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/api/workspace/scenarios/{scenario_id}/recipe/markers",
        response_model=RecipeDocumentView,
    )
    def workspace_recipe_add_marker(
        scenario_id: str, request: RollbackMarkerRequest
    ) -> RecipeDocumentView:
        return RecipeDocumentView(**recipes.add_marker(record_for(scenario_id), request))

    @app.post(
        "/api/workspace/scenarios/{scenario_id}/recipe/markers/{marker_id}/restore",
        response_model=RecipeDocumentView,
    )
    def workspace_recipe_restore_marker(
        scenario_id: str, marker_id: str
    ) -> RecipeDocumentView:
        record = record_for(scenario_id)
        try:
            return RecipeDocumentView(**recipes.restore_marker(record, marker_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/api/workspace/scenarios/{scenario_id}/recipe/undo", response_model=RecipeDocumentView)
    def workspace_recipe_undo(scenario_id: str) -> RecipeDocumentView:
        record = record_for(scenario_id)
        try:
            return RecipeDocumentView(**recipes.undo(record))
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/workspace/scenarios/{scenario_id}/recipe/redo", response_model=RecipeDocumentView)
    def workspace_recipe_redo(scenario_id: str) -> RecipeDocumentView:
        record = record_for(scenario_id)
        try:
            return RecipeDocumentView(**recipes.redo(record))
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/workspace/scenarios/{scenario_id}/frames/{mode}", response_model=POVFrameView)
    def workspace_frame(scenario_id: str, mode: str, time_s: float = 0.0) -> POVFrameView:
        if mode not in {"third-person", "in-car"}:
            raise HTTPException(status_code=422, detail="Unsupported POV mode.")
        try:
            payload = render_frame(adapter.get(scenario_id).scenario, mode=mode, time_s=time_s)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return POVFrameView(**payload)

    @app.get(
        "/api/workspace/scenarios/{scenario_id}/image-frames/{mode}",
        response_model=POVImageFrameView,
    )
    def workspace_image_frame(
        scenario_id: str, mode: str, time_s: float = 0.0
    ) -> POVImageFrameView:
        if mode not in {"third-person", "in-car"}:
            raise HTTPException(status_code=422, detail="Unsupported POV mode.")
        record = record_for(scenario_id)
        return POVImageFrameView(**esmini.image_frame(record, mode=mode, time_s=time_s))

    @app.get(
        "/api/workspace/scenarios/{scenario_id}/sensor-status",
        response_model=VariantSensorStatusView,
    )
    def workspace_sensor_status(scenario_id: str) -> VariantSensorStatusView:
        return VariantSensorStatusView(**variant_sensor_status(record_for(scenario_id), lidar))

    @app.get("/api/scenarios/{scenario_id}/artifacts")
    def scenario_artifacts(scenario_id: str):
        try:
            return {"scenario_id": scenario_id, "artifacts": adapter.artifact_links(adapter.get(scenario_id))}
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/scenarios/{scenario_id}/trajectory", response_model=TrajectoryResponse)
    def scenario_trajectory(scenario_id: str) -> TrajectoryResponse:
        try:
            return adapter.trajectory(adapter.get(scenario_id))
        except (KeyError, OSError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/api/scenarios/{scenario_id}/variants/preview", response_model=PreviewResponse)
    def preview_scenario(scenario_id: str, request: PreviewRequest) -> PreviewResponse:
        try:
            return previews.preview(scenario_id, request)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post(
        "/api/workspace/scenarios/{scenario_id}/branches",
        response_model=CanvasBranchResponse,
    )
    def create_canvas_branch(
        scenario_id: str, request: CanvasBranchRequest
    ) -> CanvasBranchResponse:
        """Commit one free-motion canvas draft for this process lifetime."""
        parent = record_for(scenario_id)
        if request.coordinate_frame != parent.scenario.coordinate_frame:
            raise HTTPException(status_code=422, detail="canvas_coordinate_frame_mismatch")
        try:
            branch = build_canvas_keyframe_branch(
                parent.scenario,
                request.actor_id,
                tuple(CanvasKeyframe(**item.model_dump()) for item in request.keyframes),
                branch_name=request.branch_name,
                seed=request.seed,
                include_origin_reference=request.include_origin_reference,
            )
            validation = validate_feasibility(branch.scenario)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not validation.valid:
            return CanvasBranchResponse(
                parent_scenario_id=scenario_id,
                scenario=adapter.summary(parent),
                validation=ValidationView(
                    valid=False,
                    validation_version=validation.validation_version,
                    reasons=[ValidationReasonView(
                        code=reason.code, category=reason.category, actor_id=reason.actor_id,
                        state_index=reason.state_index, observed=reason.observed,
                        limit=reason.limit, message=reason.message,
                    ) for reason in validation.reasons],
                ),
                artifacts=[],
                sensor_status={"status": "not_created", "reason": "canvas_branch_invalid"},
            )

        config = VariantConfig(seed=request.seed)
        branch_root = resolved_settings.output_root / "canvas-branches" / branch.scenario.scenario_id
        branch_root.mkdir(parents=True, exist_ok=True)
        scenario_path = branch_root / "scenario.json"
        scenario_path.write_text(
            json.dumps(
                variant_artifact_to_dict(branch.scenario, scenario_id, config),
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        branch_record = ArtifactRecord(
            scenario=branch.scenario,
            path=scenario_path,
            relative_path=adapter.relative_path(scenario_path),
            artifact_type="variant",
            parent_scenario_id=scenario_id,
            variant_config=config,
        )
        adapter.register_ephemeral(branch_record)
        artifacts = [ArtifactLink(
            kind="canonical-json",
            path=branch_record.relative_path,
            url=f"/api/artifacts/{branch_record.relative_path}",
        )]
        return CanvasBranchResponse(
            parent_scenario_id=scenario_id,
            scenario=adapter.summary(branch_record),
            validation=ValidationView(
                valid=True,
                validation_version=validation.validation_version,
                reasons=[],
            ),
            artifacts=artifacts,
            wasm_pair=None,
            sensor_status={
                "status": "unsupported",
                "reason": "post_edit_sensor_frames_are_not_generated_for_a_variant",
            },
        )

    @app.post(
        "/api/testing/scenarios/{scenario_id}/carla-recalculate",
        response_model=TestingPhysicsResponse,
    )
    def testing_carla_recalculate(
        scenario_id: str, request: CanvasBranchRequest
    ) -> TestingPhysicsResponse:
        """Testing-only internal physics recalculation; never a replay claim."""
        record_for(scenario_id)
        if not testing_physics_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="testing_physics_busy_retry")
        try:
            worker_env = dict(os.environ)
            worker_env["PYTHONPATH"] = str(resolved_settings.project_root / "src") + os.pathsep + worker_env.get("PYTHONPATH", "")
            completed = subprocess.run(
                (sys.executable, "-m", "r2s_web.testing_physics_worker"),
                input=json.dumps({
                    "keyframes": [item.model_dump() for item in request.keyframes],
                    "obstacles": [
                        {"x_m": actor.trajectory[0].x_m, "y_m": actor.trajectory[0].y_m, "z_m": (actor.height_m or 1.0) / 2.0}
                        for actor in record_for(scenario_id).scenario.actors
                        if actor.actor_type == "movable_object.barrier"
                    ],
                }),
                text=True,
                capture_output=True,
                timeout=90,
                cwd=resolved_settings.project_root,
                env=worker_env,
                check=False,
            )
            if completed.returncode != 0:
                detail = completed.stderr.strip() or "testing_physics_worker_failed"
                raise RuntimeError(detail[-2000:])
            payload = json.loads(completed.stdout)
        except subprocess.TimeoutExpired as error:
            raise HTTPException(status_code=409, detail="testing_physics_timeout") from error
        except (RuntimeError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        finally:
            testing_physics_lock.release()
        return TestingPhysicsResponse(**payload)

    @app.get("/api/artifacts/{artifact_path:path}")
    def download_artifact(artifact_path: str):
        try:
            path = adapter.resolve_artifact(artifact_path)
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return FileResponse(path)

    @app.post("/api/batches", response_model=JobStatus, status_code=202)
    def create_batch(request: BatchRequest) -> JobStatus:
        return batches.create(request)

    @app.get("/api/batches/{job_id}", response_model=JobStatus)
    def get_batch(job_id: str) -> JobStatus:
        try:
            return batches.get(job_id).status
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/batches/{job_id}/results", response_model=BatchResults)
    def get_batch_results(job_id: str) -> BatchResults:
        try:
            return to_results(batches.get(job_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/batches/{job_id}/results/{variant_id}", response_model=VariantResult)
    def get_batch_result(job_id: str, variant_id: str) -> VariantResult:
        try:
            result = next(
                item for item in batches.get(job_id).results if item.variant_id == variant_id
            )
        except (KeyError, StopIteration) as error:
            raise HTTPException(status_code=404, detail="Batch result was not found.") from error
        return result

    @app.post("/api/batches/{job_id}/results/{variant_id}/export", response_model=ExportResponse)
    def export_batch_result(job_id: str, variant_id: str) -> ExportResponse:
        try:
            return batches.export_variant(job_id, variant_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/batches/{job_id}/results/{variant_id}/trajectory", response_model=TrajectoryResponse)
    def get_batch_trajectory(job_id: str, variant_id: str) -> TrajectoryResponse:
        try:
            return batches.trajectory(job_id, variant_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    frontend_dist = resolved_settings.project_root / "frontend" / "dist"
    if frontend_dist.is_dir():
        # Keep the API namespace above the static mount so the image can serve
        # the compiled browser application from the same origin.
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


app = create_app()


def _settings_view(settings: WebSettings, source_scenes: SourceSceneAdapter) -> SettingsView:
    return SettingsView(
        project_root=settings.project_root.as_posix(),
        artifact_root=settings.artifact_root.as_posix(),
        output_root=settings.output_root.as_posix(),
        dataset_root=None if settings.dataset_root is None else settings.dataset_root.as_posix(),
        dataset_version=settings.dataset_version,
        artifact_root_exists=settings.artifact_root.is_dir(),
        dataset_root_exists=settings.dataset_root is not None
        and (settings.dataset_root / settings.dataset_version).is_dir(),
        source_scene_count=len(source_scenes.discover()),
    )


def _replay_view(job: ReplayJob) -> ReplayJobView:
    return ReplayJobView(
        job_id=job.job_id,
        scenario_id=job.scenario_id,
        status=job.status,
        error=job.error,
        failure_code=job.failure_code,
        failure_message=job.failure_message,
        tool_version=job.tool_version,
        exit_code=job.exit_code,
        timed_out=job.timed_out,
        stdout=job.stdout,
        stderr=job.stderr,
        artifacts={key: f"/api/artifacts/{path}" for key, path in job.artifacts.items()},
        metrics=job.metrics,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
