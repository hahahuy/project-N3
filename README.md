# Real2Scenario

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

1. Đọc [mô tả sản phẩm](docs/product-spec.md) để hiểu bài toán, phạm vi MVP và tiêu chí hoàn thành.
2. Đọc [hướng dẫn nuScenes và simulator](docs/nuscenes-and-simulation-guide.md), sau đó hoàn thành bài thực hành onboarding trong mục 11 theo ticket `R2S-100`.
3. Cài môi trường Python bằng phần **Bắt đầu nhanh**, chạy `pytest`, rồi đọc [hướng dẫn công nghệ và cách sử dụng](docs/technology-guide.md).
4. Điền data inventory, kiểm tra license, và dùng `nuscenes-devkit` render ít nhất một sample khi team đã có bộ nuScenes mini đầy đủ.
5. Chọn ticket chưa bị block trong [roadmap và danh sách ticket](docs/mvp-roadmap.md); dùng [checklist review](docs/review-checklist.md) trước khi mở pull request.

Điểm bắt đầu theo vai trò:

- Data/ML: `R2S-100`, `R2S-101`, `R2S-102`.
- Simulation: đọc guide nuScenes trước, sau đó nhận `R2S-201` đến `R2S-205`.
- UI/demo: đọc product spec và architecture trước, sau đó theo `R2S-104`, `R2S-401`.
- Reviewer/PM: bắt đầu ở product spec, roadmap checkpoint và review checklist.

## Tài liệu

- [Đặc tả sản phẩm](docs/product-spec.md)
- [Kiến trúc](docs/architecture.md)
- [Roadmap MVP và tickets](docs/mvp-roadmap.md)
- [Checklist review](docs/review-checklist.md)
- [Hướng dẫn công nghệ và cách sử dụng](docs/technology-guide.md)
- [Hướng dẫn nuScenes và mô phỏng](docs/nuscenes-and-simulation-guide.md)
- [Handoff cho agent triển khai tiếp](docs/agent-handoff.md)
- [M4 local demo architecture](docs/m4-local-demo-architecture.md)
- [Pre-M4 procedure](docs/pre-m4-procedure.md)
- [Wiki-ready CLI/API reference](docs/wiki-cli-api-reference.md)
- [Mô tả đề bài ban đầu](docs/description.md)

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

## Giấy phép dữ liệu

Dữ liệu dẫn xuất từ nuScenes trong repository này tuân theo điều khoản tại [data/LICENSE](data/LICENSE), bao gồm yêu cầu phi thương mại và ghi công. Không thêm, phân phối lại hoặc sử dụng dữ liệu ngoài các điều khoản này.
