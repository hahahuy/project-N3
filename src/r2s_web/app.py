"""FastAPI application factory for the local Real2Scenario browser demo."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .adapter import ArtifactAdapter
from .config import WebSettings
from .jobs import BatchService, to_results
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
)
from .source_scenes import SourceSceneAdapter


def create_app(settings: WebSettings | None = None) -> FastAPI:
    resolved_settings = settings or WebSettings.from_environment()
    adapter = ArtifactAdapter(resolved_settings)
    source_scenes = SourceSceneAdapter(resolved_settings)
    batches = BatchService(resolved_settings, adapter)
    app = FastAPI(title="Real2Scenario Local Demo", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.adapter = adapter
    app.state.batches = batches
    app.state.source_scenes = source_scenes
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "artifact_root_configured": resolved_settings.artifact_root.is_dir(),
            "scenario_count": len(adapter.discover()),
            "source_scene_count": len(source_scenes.discover()),
        }

    @app.get("/api/settings", response_model=SettingsView)
    def get_settings() -> SettingsView:
        return _settings_view(resolved_settings, source_scenes)

    @app.post("/api/settings", response_model=SettingsView)
    def update_settings(request: SettingsUpdateRequest) -> SettingsView:
        nonlocal resolved_settings, adapter, source_scenes, batches
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
            app.state.settings = resolved_settings
            app.state.adapter = adapter
            app.state.source_scenes = source_scenes
            app.state.batches = batches
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
