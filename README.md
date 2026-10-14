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

## Onboarding cho teammate

Người mới nên đi theo thứ tự này trước khi nhận ticket code:

1. Đọc [Plan A và current project status](MVP&ProjectSummary.md) và [documentation entrypoint](docs/README.md).
2. Đọc [nuScenes và simulator guide](docs/guides/nuscenes-and-simulation-guide.md), sau đó hoàn thành bài thực hành onboarding theo candidate dataset local.
3. Cài môi trường Python bằng phần **Bắt đầu nhanh**, chạy `pytest`, rồi đọc [technology guide](docs/guides/technology-guide.md).
4. Điền data inventory, kiểm tra license, và dùng `nuscenes-devkit` render ít nhất một sample khi team đã có dataset local. Với full/local batches, đặt `NUSCENES_ROOT=$HOME/datasets/nuscenes` và `NUSCENES_VERSION=v1.0-trainval`.
5. Chọn work item trong [current active work](docs/current/active-work.md); dùng [review checklist](docs/guides/review-checklist.md) trước khi mở pull request.

Điểm bắt đầu theo vai trò:

- Data/ML: `R2S-100`, `R2S-101`, `R2S-102`.
- Simulation: đọc guide nuScenes trước, sau đó nhận `R2S-201` đến `R2S-205`.
- UI/demo: đọc [current UI contracts](docs/current/ui-motion-editor.md) và [architecture](docs/architecture/) trước, sau đó xem các M4 evidence reports.
- Reviewer/PM: bắt đầu ở [current status](docs/current/project-status.md), [active work](docs/current/active-work.md) và [review checklist](docs/guides/review-checklist.md).

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

Scaffold ban đầu chưa phụ thuộc simulator hoặc dataset. Xem ticket Phase 0 trước khi thêm nuScenes metadata hoặc esmini.

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
