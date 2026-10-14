"""FastAPI application factory for the local Real2Scenario browser demo."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from real2scenario import state_to_dict

from .adapter import ArtifactAdapter
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
)
from .source_scenes import SourceSceneAdapter


def create_app(settings: WebSettings | None = None) -> FastAPI:
    resolved_settings = settings or WebSettings.from_environment()
    adapter = ArtifactAdapter(resolved_settings)
    source_scenes = SourceSceneAdapter(resolved_settings)
    batches = BatchService(resolved_settings, adapter)
    previews = PreviewService(resolved_settings, adapter)
    esmini = EsminiBackend(resolved_settings, adapter)
    app = FastAPI(title="Real2Scenario Local Demo", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.adapter = adapter
    app.state.batches = batches
    app.state.previews = previews
    app.state.source_scenes = source_scenes
    app.state.esmini = esmini
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
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
            "artifact_root_configured": resolved_settings.artifact_root.is_dir(),
            "scenario_count": len(adapter.discover()),
            "dataset_configured": dataset_path is not None,
            "dataset_version": resolved_settings.dataset_version,
            "dataset_metadata_available": bool(dataset_path and dataset_path.is_dir()),
        }

    @app.get("/api/settings", response_model=SettingsView)
    def get_settings() -> SettingsView:
        return _settings_view(resolved_settings, source_scenes)

    @app.get("/api/esmini")
    def esmini_capability() -> dict[str, object]:
        return esmini.capability()

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
        nonlocal resolved_settings, adapter, source_scenes, batches, previews, esmini
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
            app.state.settings = resolved_settings
            app.state.adapter = adapter
            app.state.source_scenes = source_scenes
            app.state.batches = batches
            app.state.previews = previews
            app.state.esmini = esmini
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
        )

    @app.get("/api/workspace/scenarios/{scenario_id}", response_model=ScenarioViewPayload)
    def workspace_scenario(scenario_id: str) -> ScenarioViewPayload:
        try:
            record = adapter.get(scenario_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        trajectory = adapter.trajectory(record)
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
                lidar=AvailabilityView(available=False, unavailable_reason="recorded_lidar_layer_not_implemented"),
            ),
            metrics=MetricAvailabilityView(
                available=bool(trajectory.replay_metrics),
                unavailable_reason=None if trajectory.replay_metrics else "replay_trace_not_available",
                source="replay_trace" if trajectory.replay_metrics else "none",
                per_actor=trajectory.replay_metrics,
            ),
        )

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
