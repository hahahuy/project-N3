# Real2Scenario

> **One-line summary:** An auditable pipeline that turns recorded driving interactions into replayable OpenSCENARIO scenarios, measurable simulator traces and controlled variants.

Real2Scenario chuyển các tương tác phương tiện được ghi nhận trong nuScenes thành tệp OpenSCENARIO có thể phát lại, đo độ trung thực của quá trình phát lại, và sinh các biến thể tình huống hiếm có ràng buộc.

MVP đầu tiên dùng esmini để thực thi OpenSCENARIO ở chế độ headless. Hệ thống chủ đích chỉ hỗ trợ tái dựng cục bộ theo hướng đường, không tuyên bố chuyển đổi không mất thông tin từ bản đồ nuScenes sang OpenDRIVE.

## Phạm vi hiện tại

- Schema scenario chuẩn, độc lập với simulator.
- Trích xuất quỹ đạo nuScenes khi metadata cần thiết đã có ở máy cục bộ.
- Xuất baseline OpenSCENARIO và phát lại bằng esmini.
- Biến đổi có kiểm soát về tốc độ, khoảng cách và thời điểm.
- Validation, metric quỹ đạo và báo cáo scenario có thể review.

## Agent onboarding: start here

Read the current context before changing code. The current MVP is nuScenes
`v1.0-trainval` -> a scene-local `scene-0061` corridor -> OpenDRIVE/
OpenSCENARIO -> esmini replay/evaluation -> metrics and diagnostic gates ->
dynamic object variation -> an internal kinematic preview -> the full 2D/3D
authoring workspace -> optional recorded LiDAR evidence. CARLA is post-MVP and
same-XOSC CARLA execution is not current MVP evidence.

### Required reading order

1. [MVP & Project Summary](MVP&ProjectSummary.md): Plan A scope and checkpoint intent.
2. [Documentation entrypoint](docs/README.md): documentation rules and directory map.
3. [PM agent guide](docs/current/pm-agent-guide.md): ownership, status vocabulary and workflow.
4. [Current project status](docs/current/project-status.md): latest checkpoint state, evidence and risks.
5. [Decision log](docs/current/decisions.md): approved scope, simulator and physics decisions.
6. [Active work queue](docs/current/active-work.md): dependencies, acceptance evidence and next agents.
7. [Technical contracts](docs/current/technical-contracts.md): CP1/CP2, preview/frame and `kinematic-open-loop-v1` contracts.
8. [Evidence index](docs/current/evidence-index.md): claim-to-report mapping and unverified claims.
9. [Artifact policy](docs/current/artifact-policy.md): license, privacy and local/private artifact boundaries.
10. [Next-agent handoff](docs/current/next-agent-handoff.md): repository checks and the assigned first task.

Read only the relevant follow-up handoff after the common context:

- CP1 semantic alignment: [CP1 agent handoff](docs/current/cp1-agent-handoff-next.md) and the linked CP1 reports.
- UI and authoring: [UI motion editor](docs/current/ui-motion-editor.md), [MVP UI flow](docs/current/ui-mvp-flow-spec.md), and [U0 showcase](docs/current/ui-showcase-checkpoint.md).
- Simulator work: [technical contracts](docs/current/technical-contracts.md), especially the MVP physics budget and Tier 1 `kinematic-open-loop-v1`.
- PM/review work: [PM guide](docs/current/pm-agent-guide.md), [active work](docs/current/active-work.md), and [review checklist](docs/guides/review-checklist.md).

Do not use `docs/archive/plan-b/` as current scope. It is historical context
only. Reports under `docs/reports/` and evidence under `docs/evidence/` support
claims but do not override current decisions.

### First repository checks

Run these commands from the repository root before implementation:

```bash
git status --short
git log --oneline -10
python --version
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_docs_consistency.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

The expected baseline is a passing documentation checker and passing Python
suite. Record differences before editing. Do not reset or overwrite unrelated
worktree changes.

### Current next work

The active implementation sequence is:

1. CP1 owner interpretation and cross-scene semantic confirmation, preserving the immutable `20/143 = 13.99%` baseline.
2. CP3 owner-approved benchmark index/protocol and provisional benchmark evidence.
3. CP5 owner sign-off and verified-tree release evidence.
4. Tier 1 `kinematic-open-loop-v1` internal simulator with normalized traces, explicit limit diagnostics and collision pre-checks.
5. Full 2D/3D authoring workspace and frame-aware timeline.
6. Post-edit frame generation and optional recorded LiDAR evidence.
7. CP6 paper evidence.

Do not silently change Plan A, actor scope, lane direction, tolerances, ground
truth policy, same-XOSC requirements, licensing boundaries or final scientific
thresholds. Every completed work item needs tests, evidence, status updates and
an English completion report.

## Tài liệu

- [Documentation entrypoint](docs/README.md)
- [Current project status](docs/current/project-status.md)
- [Current decisions](docs/current/decisions.md)
- [Current technical contracts](docs/current/technical-contracts.md)
- [Active work queue](docs/current/active-work.md)
- [Evidence index](docs/current/evidence-index.md)
- [Artifact policy](docs/current/artifact-policy.md)
- [OSM integration proposal](docs/current/osm-integration-proposal.md)
- [Migration checklist](docs/plan-a-migration-checklist.md)
- [Guides](docs/guides/)
- [Architecture](docs/architecture/)
- [Reports](docs/reports/)

## Bắt đầu nhanh

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The repository now contains the current MVP implementation and its supporting
contracts. Use the onboarding sequence above rather than historical Phase 0
ticket assumptions.

## Local M4 web demo

The M4 browser demo uses FastAPI plus React and keeps all scenario processing on
the current machine. It does not require nuScenes data or esmini for the
synthetic smoke path.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,web]"
uvicorn r2s_web.app:app --app-dir src --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Configure `R2S_ARTIFACT_ROOT` and
`R2S_OUTPUT_ROOT` before starting the backend when using local artifacts; both
paths are project-relative by default (`scenarios` and `reports`). The frontend
never reads those files directly. The optional `ESMINI_BIN` and
`ESMINI_DAT2CSV` environment variables enable replay and are never stored in
source or committed documentation.

The synthetic API smoke test copies
`tests/fixtures/synthetic-variant-artifact.json` into a temporary artifact root,
loads the scenario, renders recorded trajectories, generates a deterministic
20-variant grid, validates before ranking, and exercises the distinct
`simulator-failed` state when esmini is unavailable.

When the local `data/v1.0-mini` release is present, open `LOCAL PATHS` in the
browser to point the demo at an artifact directory and dataset root. The UI
will list the ten local nuScenes scenes and can import a selected scene into a
canonical `local_road_aligned` baseline before generation. Imported files are
written under `scenarios/nuscenes/`, which is ignored by git.

## Docker deployment

The production-style image builds the React bundle and serves it from the same
FastAPI process as the API. It does not include esmini; mount or install the
optional simulator tools separately and set `ESMINI_BIN` and `ESMINI_DAT2CSV`
when replay is required.

```bash
docker build -t real2scenario:local .
docker run --rm -p 8000:8000 \
  -v "$(pwd)/reports:/app/reports" \
  -e ESMINI_BIN=/opt/esmini/esmini \
  -e ESMINI_DAT2CSV=/opt/esmini/dat2csv \
  real2scenario:local
```

Open `http://localhost:8000`. For local scenario imports or replay, mount the
corresponding host directories and simulator binaries into the container. The
container is intentionally a single-user local deployment, matching the M4
architecture and M5A scope; it does not add a database, queue, or shared
storage service.

## Remote development with Docker

Use `compose.dev.yml` on the development host for live backend reload and
frontend HMR. Source files are bind-mounted, so normal code edits do not
require image rebuilds. The frontend proxies `/api` to the backend, so remote
review only needs the frontend URL.

```bash
docker compose -f compose.dev.yml up -d --build
docker compose -f compose.dev.yml logs -f
```

Open `http://hhf-server:5173` over Tailscale. The backend is also exposed for
direct checks at `http://hhf-server:${R2S_WEB_API_PORT:-8001}`. If port 8000 is
available on the host, run with `R2S_WEB_API_PORT=8000` to use the original API
port. Do not stop another service already using that port.

Rebuild only when dependencies or Dockerfiles change:

```bash
docker compose -f compose.dev.yml up -d --build
```

For M5A, configure `ESMINI_BIN` and `ESMINI_DAT2CSV` in the shell environment
before starting Compose if the default `~/esmini/bin` locations do not apply.
The default Compose configuration mounts `~/esmini` read-only and uses
`/opt/esmini/bin/esmini` and `/opt/esmini/bin/dat2csv`. The current stack keeps esmini optional;
M5A still needs capability discovery, a focused backend, asynchronous replay
jobs, structured simulator artifacts, and fake-executable tests.

## Giấy phép dữ liệu

Source code của `project-N3` được phát hành theo Apache-2.0, xem `LICENSE` và
`NOTICE`. Apache-2.0 không áp dụng cho dữ liệu nuScenes, map assets hoặc bất kỳ
trajectory, `.xosc`, `.xodr`, replay CSV/PNG/video hay artifact nào dẫn xuất từ
nuScenes. Các artifact này là local/private only và vẫn tuân theo điều khoản
nuScenes tại `data/v1.0-mini/LICENSE`; không thêm hoặc phân phối lại chúng nếu
chưa có quyết định phát hành riêng bằng văn bản.
