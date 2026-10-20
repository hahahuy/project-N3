# Real2Scenario: Tài liệu đặc tả và thiết kế

Status: `REFERENCE` · Cập nhật: 2026-10-17

Tài liệu này tổng hợp yêu cầu và thiết kế của hệ thống từ các tài liệu hiện hành.
Nó **không** thay thế các nguồn gốc: khi có mâu thuẫn, `docs/current/decisions.md`
và `docs/current/technical-contracts.md` là căn cứ. Mọi số liệu đo được giữ nguyên
nhãn `PROVISIONAL` như ở nguồn.

Sơ đồ kiến trúc: [`architecture-diagram.html`](architecture-diagram.html).

## Mục lục

1. [Giới thiệu](#1-giới-thiệu)
2. [Tổng quan sản phẩm](#2-tổng-quan-sản-phẩm)
3. [Yêu cầu chức năng](#3-yêu-cầu-chức-năng)
4. [Yêu cầu phi chức năng](#4-yêu-cầu-phi-chức-năng)
5. [Kiến trúc hệ thống](#5-kiến-trúc-hệ-thống)
6. [Thiết kế dữ liệu](#6-thiết-kế-dữ-liệu)
7. [Thiết kế API](#7-thiết-kế-api)
8. [Thiết kế module](#8-thiết-kế-module)
9. [Thiết kế runtime mô phỏng](#9-thiết-kế-runtime-mô-phỏng)
10. [Đánh giá: metric và gate](#10-đánh-giá-metric-và-gate)
11. [Triển khai và vận hành](#11-triển-khai-và-vận-hành)
12. [Bảo mật, dữ liệu và giấy phép](#12-bảo-mật-dữ-liệu-và-giấy-phép)
13. [Kiểm thử](#13-kiểm-thử)
14. [Hiện trạng theo checkpoint](#14-hiện-trạng-theo-checkpoint)
15. [Rủi ro, giới hạn và ranh giới tuyên bố](#15-rủi-ro-giới-hạn-và-ranh-giới-tuyên-bố)
16. [Tài liệu nguồn](#16-tài-liệu-nguồn)

---

## 1. Giới thiệu

### 1.1 Mục đích

Real2Scenario là pipeline có thể kiểm chứng, chuyển tương tác phương tiện ghi thật
trong nuScenes thành kịch bản **OpenSCENARIO** (`.xosc`) phát lại được, đo độ
trung thực của việc phát lại, và sinh các biến thể tình huống hiếm có ràng buộc.

### 1.2 Phạm vi MVP

| Trong phạm vi | Ngoài phạm vi (post-MVP / tương lai) |
|---|---|
| nuScenes `v1.0-trainval`, khu vực Singapore One-North | Phủ cả 4 khu vực bản đồ nuScenes |
| Corridor OpenDRIVE cục bộ quanh `scene-0061` (DEC-008) | Chuyển đổi bản đồ nuScenes → OpenDRIVE không mất thông tin |
| Phát lại bằng esmini (headless) + preview động học nội bộ (DEC-011) | Thực thi CARLA same-XOSC (giữ hợp đồng DEC-002) |
| Biến thể tốc độ, khoảng cách, thời điểm; chỉnh actor động (DEC-012) | Behavior executor, closed-loop với planner |
| Gate G1–G7, metric ADE/FDE, báo cáo phễu | Mô phỏng cảm biến, neural reconstruction |
| Workspace 2D/3D trên trình duyệt, LiDAR ghi thật làm bằng chứng | Sinh khung cảm biến sau chỉnh sửa |
| | Dataset thứ hai (Waymo Open Motion là ứng viên, DEC-010) |

### 1.3 Đối tượng đọc

Quản lý dự án, giám khảo, kỹ sư backend/frontend và agent tiếp nhận công việc.

### 1.4 Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| OpenSCENARIO (`.xosc`) | Chuẩn ASAM mô tả hành vi động của kịch bản |
| OpenDRIVE (`.xodr`) | Chuẩn ASAM mô tả mạng đường |
| esmini | Trình chạy OpenSCENARIO mã nguồn mở, dùng làm công cụ đo |
| Canonical scenario | Mô hình `Scenario` độc lập simulator trong `real2scenario.models` |
| ADE / FDE | Sai số dịch chuyển trung bình / cuối giữa quỹ đạo phát lại và ground truth |
| Road-match | Tỷ lệ trạng thái actor nằm trong làn `.xodr` |
| Gate G1–G7 | Các tầng lọc biến thể, từ rẻ đến đắt |
| Tier 0 / 1 / 2 | Các tầng runtime mô phỏng tách biệt (DEC-014) |
| Provenance | Siêu dữ liệu truy vết nguồn: token, timestamp, khung tọa độ, phiên bản công cụ |
| CP0–CP6 | Các checkpoint nghiệm thu của dự án |

## 2. Tổng quan sản phẩm

### 2.1 Bài toán

Dữ liệu lái xe thật hiếm khi có tình huống nguy hiểm (cut-in gấp, phanh gấp).
Chưa có pipeline mã nguồn mở nào làm trọn chuỗi nuScenes → OpenDRIVE →
OpenSCENARIO → biến thể → đo sai số phát lại. Giá trị chính của dự án là **tính
minh bạch và khả năng kiểm chứng**, không phải hình ảnh mô phỏng đẹp.

### 2.2 Người dùng

| Vai trò | Nhu cầu |
|---|---|
| Nhà nghiên cứu xe tự hành | Tạo kịch bản kiểm thử từ dữ liệu thật, có số liệu fidelity |
| Kỹ sư kiểm thử mô phỏng | Sinh và lọc biến thể hiếm, tải `.xosc/.xodr` |
| Giám khảo / reviewer | Xem demo, kiểm tra claim dựa trên bằng chứng |

### 2.3 Giả định và ràng buộc

- Dữ liệu nuScenes có sẵn cục bộ tại `$NUSCENES_ROOT` (mặc định `/mnt/backup/nuscenes`).
- Python 3.12 trong `.venv/` (yêu cầu tối thiểu `>=3.11`); esmini v3.9.0 cho phép đo.
- Ground truth là annotation và ego pose thô tại keyframe (~2 Hz), không phải quỹ đạo đã làm mượt (DEC-004).
- nuScenes không có ground truth về lái, lốp, treo, động cơ, nên mọi claim động lực học nằm ngoài MVP.

## 3. Yêu cầu chức năng

Trạng thái: **Đã có** = đã triển khai và có test; **Một phần** = triển khai nhưng
chưa nghiệm thu; **Chưa** = chưa triển khai hoặc bị tắt có chủ đích.

| ID | Yêu cầu | Thành phần chính | Trạng thái |
|---|---|---|---|
| FR-01 | Khám phá và import cảnh nuScenes cục bộ | `source_scenes.py`, `MetadataIndex` | Đã có |
| FR-02 | Trích xuất quỹ đạo ego và actor thành `Scenario` toàn cục | `ingestion.py`, `nuscenes_backend.py` | Đã có |
| FR-03 | Biến đổi sang khung cục bộ theo đường, giữ provenance | `coordinates.py` | Đã có |
| FR-04 | Dựng corridor OpenDRIVE quanh cảnh, đo road-match | `mapbuilder`, `road_match.py` | Một phần (13.99%) |
| FR-05 | Xuất `.xosc` dùng template `.xodr` | `exporter.py`, `templates/` | Đã có |
| FR-06 | Phát lại bằng esmini, chuẩn hóa trace | `simulation.py`, `r2s_web/esmini.py` | Đã có |
| FR-07 | Tính ADE/FDE, sai số heading, tốc độ; aggregate đa cảnh | `metrics.py`, `benchmark.py` | Một phần (thiếu scene-macro) |
| FR-08 | Sinh biến thể grid/random tất định (tốc độ, gap, timing) | `generation.py`, `jobs.py` | Đã có |
| FR-09 | Chỉnh actor bằng recipe có ràng buộc, undo/redo, rollback | `recipe.py`, Recipe editor | Đã có (in-process) |
| FR-10 | Preview động học Tier 1, báo vi phạm giới hạn | `kinematic.py`, `validation.py` | Đã có |
| FR-11 | Đánh giá gate G1–G7 và báo cáo phễu | `gates.py`, `reporting.py` | Một phần (G6/G7 provisional) |
| FR-12 | Xếp hạng biến thể theo rủi ro, mới lạ, chất lượng replay | `ranking.py` | Đã có |
| FR-13 | Workspace: tối đa 3 pane, 5 loại view, timeline, Compare | `frontend/src/App.tsx` | Đã có |
| FR-14 | Hiển thị LiDAR `LIDAR_TOP` ghi thật làm bằng chứng | `lidar.py`, `nuscenes_adapter.py` | Đã có |
| FR-15 | Phiên esmini live native, luồng trạng thái | `live_session.py` | Một phần (không có control ABI) |
| FR-16 | Preview esminiJS (WASM) trên trình duyệt | `/wasm-smoke` | Diagnostic (DEC-020) |
| FR-17 | Tải artifact `.xosc/.xodr` qua route có kiểm soát | `adapter.py` | Đã có |
| FR-18 | Nút Behavior / Validate / Replay trong workspace | Toolbar | Chưa (tắt có chủ đích, DEC-016) |
| FR-19 | Thực thi CARLA same-XOSC | `carla_*.py` | Chưa (post-MVP) |

## 4. Yêu cầu phi chức năng

| ID | Nhóm | Yêu cầu |
|---|---|---|
| NFR-01 | Kiểm chứng | Mọi artifact mang provenance: token nguồn, timestamp, khung tọa độ, phiên bản công cụ |
| NFR-02 | Trung thực | Dữ liệu thiếu là trạng thái `unavailable` có tên, không bao giờ là `0` hay response rỗng thành công |
| NFR-03 | Tất định | Sinh biến thể tất định theo `seed`; aggregate theo thứ tự cảnh cố định |
| NFR-04 | Bất biến | Sinh biến thể và recipe không sửa kịch bản cha hay artifact gốc |
| NFR-05 | Không clamp ngầm | Validation báo vi phạm, không tự sửa giá trị; mọi phép chiếu phải có provenance |
| NFR-06 | Tách lớp | Domain không import FastAPI/React; adapter không để lộ object thô của vendor |
| NFR-07 | Độ chính xác số | Tích phân esmini `--fixed_timestep 0.01` (đã hội tụ: `0.005` cho kết quả giống hệt) |
| NFR-08 | Hiệu năng | Đổi timestep `0.05 → 0.01` chấp nhận chi phí runtime +14% |
| NFR-09 | Bảo mật | Chặn path traversal; không lộ đường dẫn dataset riêng qua API; demo public đứng sau basic-auth |
| NFR-10 | Giấy phép | Mã nguồn Apache-2.0; dữ liệu nuScenes và dẫn xuất ở local/private |
| NFR-11 | Khả năng tái lập | Lockfile phụ thuộc, manifest benchmark, bundle bằng chứng release (CP5) |
| NFR-12 | Truy cập | UI dùng được bằng bàn phím, màn hình hẹp, tôn trọng reduced-motion |
| NFR-13 | Tài nguyên | Container `api` giới hạn 4 CPU / 12 GB; gateway 0.5 CPU / 256 MB |

## 5. Kiến trúc hệ thống

Xem sơ đồ chi tiết ở [`architecture-diagram.html`](architecture-diagram.html).

### 5.1 Bốn lớp runtime

```text
React workspace (frontend/src/)
    -> FastAPI routes và web services (src/r2s_web/)
        -> canonical artifacts và domain services (src/real2scenario/)
            -> dataset/simulator adapters
                -> nuScenes metadata, sensor data, maps và esmini
```

### 5.2 Quy tắc phụ thuộc

```text
frontend -> r2s_web -> real2scenario
                         ^
                         |
             dataset/simulator adapters
```

| Lớp | Sở hữu | Không được làm |
|---|---|---|
| Frontend | Trình bày, trạng thái tương tác, vòng đời request | Tự suy ra sự thật domain, thay dữ liệu thiếu, đọc file trực tiếp |
| `r2s_web` | Route, điều phối, khối availability, lỗi API | Định nghĩa lại vật lý canonical, che lỗi dữ liệu ngoài |
| `real2scenario` | Model canonical, ingestion, generation, validation, gate, replay, metric | Phụ thuộc FastAPI, React, trạng thái trình duyệt |
| Dataset adapter | Dịch bản ghi nguồn sang dữ liệu canonical + provenance | Để lộ object thô của vendor trong hợp đồng public |
| Simulator adapter | Gọi esmini/binding native, chuẩn hóa trạng thái và trace | Gọi transform trình duyệt là ảnh simulator, âm thầm chuyển sang simulator khác |
| Artifact boundary | Kiểm tra, đọc, ghi artifact | Sửa kịch bản cha ngầm, bỏ qua giới hạn đường dẫn |

### 5.3 Hướng mở rộng nền tảng

Biên ổn định cho tương lai đa dataset (DEC-009, DEC-010):

```text
dataset adapter
  -> canonical scenario + source provenance
  -> normalized map/geometry provider
  -> OpenSCENARIO/export contract
  -> simulator backend/trace contract
  -> evaluator/gates/reports/UI
```

## 6. Thiết kế dữ liệu

### 6.1 Mô hình canonical (`real2scenario/models.py`)

| Lớp | Trường chính |
|---|---|
| `State` | `time_s`, `x_m`, `y_m`, `yaw_rad`, `speed_mps`, `source_timestamp_us?`, `source_record_token?` |
| `Actor` | `actor_id`, `actor_type`, `trajectory: tuple[State]`, `length_m?`, `width_m?`, `height_m?` |
| `InteractionEvent` | `label`, `actor_ids`, `start_time_s`, `end_time_s`, `derivation`, `confidence?` |
| `VariantConfig` | `speed_multiplier=1.0`, `initial_gap_delta_m=0.0`, `timing_offset_s=0.0`, `seed=0` |
| `Scenario` | `scenario_id`, `duration_s`, `ego_actor_id`, `actors`, `coordinate_frame`, `provenance`, `replay_mode="open_loop_trajectory"`, `interaction_events` |

**Bất biến:**

- Giá trị `State` hữu hạn, thời gian không âm.
- Timestamp của mỗi actor tăng nghiêm ngặt.
- `actor_id` là duy nhất và có chứa ego đã khai báo.
- `duration_s` bao phủ mọi quỹ đạo actor.
- Serialization kiểm tra version schema, trường bắt buộc và provenance.

### 6.2 Artifact

| Artifact | Định dạng | Vị trí |
|---|---|---|
| Baseline scenario | JSON có version (`serialization.py`) | `artifact_root` (private) |
| Kịch bản phát lại | `.xosc` + `.xodr` | `artifact_root` / report dir (private) |
| Replay trace | `normalized-replay-trace-v2` | report dir (private) |
| Báo cáo biến thể / batch | JSON + phễu gate | `reports/` |
| Aggregate benchmark | `benchmark-aggregate-v1` | `reports/`, không ghi đường dẫn host |
| Bằng chứng G3 | `lane-road-match-evidence-v1` | theo từng biến thể |

### 6.3 Hợp đồng có version

`kinematic-open-loop-v1`, `normalized-replay-trace-v2`, `esmini-live-session-v1`,
`nuscenes-sensor-evidence-v1`, `workspace-variant-sensor-v1`,
`workspace-pov-image-v1`, `benchmark-aggregate-v1`, `lane-road-match-evidence-v1`.
Định nghĩa đầy đủ trong `docs/current/technical-contracts.md`.

## 7. Thiết kế API

FastAPI dùng namespace phẳng `/api`. Route chính thức nằm trong `src/r2s_web/app.py`.

| Nhóm | Route |
|---|---|
| Catalog & artifact | `GET /api/scenarios`, `/api/scenarios/{id}`, `/trajectory`, `/artifacts`, `GET /api/artifacts/{path}` |
| Workspace | `GET /api/workspace/scenarios/{id}` và `/timeline`, `/gate-timeline`, `/lineage`, `/compare`, `/frames/{mode}`, `/image-frames/{mode}`; `GET/POST .../recipe/...` |
| Dataset & bằng chứng | `GET /api/source-scenes`, `POST /api/source-scenes/{token}/import`, `/lidar`, `/lidar-sweeps`, `/sensor-evidence`, `/top-down`, `/top-down-state`, `/ground-layers`, `/camera-evidence`, `GET /api/workspace/camera-image/{token}`, `/maps/{map}/...`, `POST .../wasm-pair` |
| Mô phỏng & sinh | `POST/GET /api/replays...`, `POST /api/batches`, `GET /api/batches/{job}/results...`, `POST /api/scenarios/{id}/variants/preview`, `POST/GET/DELETE /api/esmini/live/...` |
| Vận hành | `GET /api/health` |

**Luồng xử lý một request:**

```text
HTTP request -> Pydantic request model -> tra cứu và ánh xạ lỗi trong route
  -> web service -> domain model / adapter -> response model hoặc payload unavailable rõ ràng
```

Quy tắc: lỗi domain dự kiến → HTTP response ổn định; exception bất ngờ **không**
được biến thành trạng thái unavailable thành công. Thêm route phải cập nhật
Pydantic schema, API test, helper frontend và register hợp đồng.

## 8. Thiết kế module

### 8.1 Scenario core (`src/real2scenario/`)

| Module | Trách nhiệm |
|---|---|
| `models.py`, `serialization.py` | Model canonical, bất biến, JSON có version và provenance |
| `ingestion.py`, `nuscenes_backend.py`, `metadata_index.py` | nuScenes → `Scenario` toàn cục; cache metadata theo cảnh |
| `coordinates.py` | Biến đổi tọa độ, giữ `source_timestamp_us` / `source_record_token` |
| `mapbuilder/`, `road_match.py` | Corridor OpenDRIVE, đo road-match |
| `generation.py` | Biến thể grid/random tất định, preview chỉnh sửa |
| `validation.py`, `kinematic.py` | Khả thi động học, Tier 1 preview |
| `gates.py`, `ranking.py` | G1–G7, tóm tắt phễu, xếp hạng |
| `exporter.py`, `xosc_subset.py`, `templates.py` | Xuất và phân tích subset OpenSCENARIO |
| `simulation.py`, `metrics.py` | Gọi esmini, parse trace, ADE/FDE |
| `reporting.py`, `benchmark.py`, `packaging.py`, `preflight.py` | Báo cáo, aggregate, gói phát hành, kiểm tra môi trường |
| `carla_*.py` | Planner CP2-A cho CARLA (post-MVP) |

**Pipeline xử lý:**

```text
source metadata -> ingestion -> Scenario -> coordinate transform -> baseline artifact
  -> generation / preview -> validation -> gates và ranking -> export / replay / metrics / report
```

### 8.2 Web backend (`src/r2s_web/`)

| Module | Trách nhiệm |
|---|---|
| `app.py` | App factory, route, middleware, mount SPA tĩnh |
| `schemas.py` | Hợp đồng Pydantic |
| `adapter.py` | `ArtifactAdapter.resolve_artifact()`: biên đọc artifact |
| `config.py` | `WebSettings.with_paths()`: giới hạn thư mục người dùng chọn |
| `jobs.py` | Batch sinh biến thể, điều phối preview |
| `recipe.py` | `RecipeStore` in-process, không phá hủy |
| `esmini.py` | Replay subprocess bất đồng bộ, tra ảnh |
| `live_session.py` | `LiveSessionService`: giới hạn file XOSC/XODR, định danh SHA-256, tuần tự hóa phiên native vì esminiLib dùng trạng thái toàn cục |
| `lidar.py`, `native_map.py`, `nuscenes_adapter.py` | LiDAR riêng tư đã decimate, map chỉ đọc, devkit |
| `frames.py`, `*_timeline.py`, `compare.py`, `lineage.py`, `evidence_layers.py` | Phép chiếu dữ liệu cho workspace |
| `camera.py`, `camera_projection.py` | Bằng chứng camera chỉ để hiển thị, phép chiếu kiểu nuScenes cho overlay preview |
| `ground.py`, `topdown.py`, `preview_time.py` | Lớp mặt đất (vỉa hè, vạch qua đường) cho WASM preview, ghép trạng thái top-down, chọn thời điểm cho bằng chứng preview |

### 8.3 Frontend (`frontend/src/`)

| File | Trách nhiệm |
|---|---|
| `App.tsx` | Shell workspace, trạng thái UI, các vùng tính năng (cố ý giữ phẳng) |
| `api.ts` | Helper request và kiểu response |
| `styles.css` | Token giao diện, responsive, reduced-motion |
| `icons.tsx`, `main.tsx` | Bộ icon SVG, điểm mount |

Vùng tính năng: Catalog, Workspace views (`MAX_VIEWS = 3`; Top-down, Sensor
Evidence, 3rd-person POV mặc định, In-car POV, LiDAR 3D), Timeline, Recipe,
Compare, Sensor Evidence, Live state.

**Quy tắc UI:** không dùng giá trị số thiếu như số 0; hiển thị nguyên trạng thái
và lý do unavailable từ backend; không gọi frame transform trình duyệt là ảnh simulator.

### 8.4 Adapters

| Adapter | Code | Đầu ra |
|---|---|---|
| nuScenes ingestion | `ingestion.py`, `nuscenes_backend.py` | `Scenario` + provenance nguồn |
| Metadata cache | `metadata_index.py` | Bảng theo cảnh kèm trạng thái cache |
| nuScenes devkit | `r2s_web/nuscenes_adapter.py` | LiDAR, box, map, transform, CAN |
| Native map | `r2s_web/native_map.py` | Bản ghi map đã chuẩn hóa, chỉ đọc |
| esmini subprocess | `simulation.py`, `r2s_web/esmini.py` | Trace chuẩn hóa, artifact riêng tư |
| esmini native | `r2s_web/live_session.py` | Hợp đồng phiên trạng thái có giới hạn |

Devkit nuScenes chính thức là nguồn ngữ nghĩa cho cảm biến, annotation, map và
CAN (DEC-015). Adapter lazy-load phụ thuộc tùy chọn và báo rõ lý do unavailable.

## 9. Thiết kế runtime mô phỏng

Ba tầng tách biệt (DEC-014), cộng hai đường phụ:

| Tầng | Thành phần | Vai trò | Ràng buộc |
|---|---|---|---|
| Tier 0 | esmini subprocess, open-loop | Công cụ đo ADE/FDE duy nhất được công nhận (DEC-018) | `followingMode=position`, `--fixed_timestep 0.01` |
| Tier 1 | `kinematic-open-loop-v1` | Preview authoring, G4/G5, kiểm tra va chạm sơ bộ | dt `0.05 s`, giới hạn gia tốc/giảm tốc/jerk/yaw-rate tường minh; trace tương thích `normalized-replay-trace-v2` |
| Tier 2 | Controller, bicycle model | Thử nghiệm gần động lực học | Post-MVP, chỉ diagnostic, không được trình bày như replay |
| Live | esminiLib native | Trạng thái live cho POV | Phiên tuần tự; reset bằng nạp lại cặp file; control `esminiLib_control_abi_unavailable` |
| WASM | esminiJS trong Web Worker | Dự kiến thay runner hiện tại | Diagnostic tại `/wasm-smoke`; Worker giữ đồng hồ dt `0.01`; seek = reset + tích phân lại từ `t=0`; không phải nguồn metric |

**Nguyên tắc cốt lõi:** biến thể sinh ra phải được đánh giá qua đường replay Tier 0,
không được chấm điểm bằng chính mô hình preview đã tạo ra nó.

## 10. Đánh giá: metric và gate

### 10.1 ADE/FDE

- **Ground truth:** annotation/ego pose thô tại keyframe.
- **Căn thời gian:** lấy mẫu trace esmini đúng timestamp keyframe bằng nội suy tuyến tính, cùng hệ tọa độ.
- **ADE:** trung bình khoảng cách Euclid theo thời gian của từng actor. **FDE:** khoảng cách tại thời điểm cuối.
- **Báo cáo:** mean, median, p95, max. FDE thiếu giữ là `null`, không phải 0.
- **Chỉ số phụ:** sai số heading (role A), `speed_mae_mps` (role B vì tốc độ canonical là sai phân hữu hạn).

**Baseline hiện hành** (`PROVISIONAL`; 850 cảnh, 3215 track, esmini v3.9.0, commit `b52d423`/`79a4a8a`/`3372ff0`):

| ADE mean | ADE median | ADE p95 | ADE max | FDE max | Cảnh hợp lệ |
|---|---|---|---|---|---|
| 0.0411 m | 0.0348 m | 0.1035 m | 0.1726 m | 0.2052 m | 808/850 |

Số này đo trên lưới danh tính (kịch bản không chỉnh sửa): chứng minh esmini tái
tạo đúng quỹ đạo được đưa vào, **không** chứng minh bản đồ đúng vị trí thật.
Mọi số ADE/FDE trước `b52d423` đều vô hiệu. Chưa đề xuất ngưỡng vì aggregate mới
có micro mean, còn thiếu scene-macro.

### 10.2 Gate G1–G7

Mỗi gate trả về `pass | fail | skipped | error` kèm lý do và `config_version`.
Gate chỉ báo trạng thái từ bằng chứng tường minh đã kiểm tra (fail-closed).

| Gate | Điều kiện | Cài đặt | Trạng thái |
|---|---|---|---|
| G1 | `.xosc` hợp lệ theo subset OpenSCENARIO được hỗ trợ | `evaluate_g1_xosc` → `parse_xosc_subset` | Đã có |
| G2 | esmini nạp và chạy hết kịch bản | `evaluate_g2_simulator_completion` | Đã có |
| G3 | Road-match ≥ 0.95 (cố định, caller không đổi được) | `evaluate_g3_road_match` | Đã đánh giá 60 ứng viên, 0 đạt |
| G4 | Gia tốc, jerk, tốc độ trong giới hạn | Tier 1 | Đã có |
| G5 | Không va chạm ngoài ý muốn trước sự kiện chính | Sự kiện do operator khai báo | Đã có; thiếu khai báo → `skipped` |
| G6 | Đủ hiếm: TTC/khoảng cách tối thiểu dưới ngưỡng | `evaluate_temporary_g6_g7` | `PROVISIONAL`, luôn fail do cài đặt |
| G7 | Đa dạng: loại bản trùng | `evaluate_temporary_g6_g7` | `PROVISIONAL` |

Phễu (`summarize_gate_funnel`) báo số được đánh giá, số đạt và số đạt tích lũy
qua từng gate. Số "kịch bản hợp lệ" là đầu ra của G7.

## 11. Triển khai và vận hành

| Môi trường | File | Thành phần |
|---|---|---|
| Dev | `compose.dev.yml` | `api` (uvicorn `--reload`), `frontend` (Vite dev server) |
| Demo/prod | `compose.demo.yml` (`make prod`) | `cloudflared` → `gateway` (nginx, TLS, basic-auth) → `api` (uvicorn, healthcheck `/api/health`), job `api-permissions` |

- Chỉ gateway được publish; FastAPI phục vụ cả `/api/*` và SPA đã build.
- Truy cập public qua Cloudflare Tunnel tại `https://project-n3.hahuy.cloud`.
- Volume có tên cố định: `project-n3-metadata-cache`, `project-n3-prod-scenarios`, `project-n3-prod-reports`, `project-n3-prod-logs`.
- Dataset và esmini mount chỉ đọc; biến môi trường `NUSCENES_ROOT`, `ESMINI_BIN`, `ESMINI_DAT2CSV`, `ESMINILIB_PATH`.

Chạy cục bộ không cần nuScenes/esmini (đường synthetic):

```bash
python -m pip install -e ".[dev,web]"
uvicorn r2s_web.app:app --app-dir src --reload --port 8000
```

## 12. Bảo mật, dữ liệu và giấy phép

- Mã nguồn: Apache-2.0. Dữ liệu nuScenes thô và mọi dẫn xuất (`.xodr`, `.xosc`, quỹ đạo, trace, ảnh) ở local/private, không commit (DEC-005).
- `ArtifactAdapter` và `WebSettings.with_paths()` chặn truy cập ngoài thư mục cho phép.
- `LiveSessionService` giới hạn file XOSC/XODR và định danh bằng SHA-256.
- API không lộ đường dẫn dataset riêng; LiDAR chỉ trả byte đã decimate kèm metadata.
- Demo public: basic-auth tại nginx, file htpasswd mount trực tiếp chỉ đọc, token tunnel trong `ops/demo/.env` (bị `.gitignore`).
- Việc còn lại cho public exposure (ví dụ giới hạn concurrency batch): `docs/current/demo-hardening-backlog.md`.

## 13. Kiểm thử

| Lớp | Lệnh | Test chính |
|---|---|---|
| Python (domain + web) | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` | `tests/` (models, serialization, ingestion, generation, validation, gates, simulation, metrics, metadata, mapbuilder, web API, live session) |
| Frontend | `cd frontend && npm test -- --run && npm run build` | `api.test.ts`, `workspace.test.tsx` |
| Browser smoke | `node scripts/workspace_browser_smoke.mjs` | Luồng workspace thật |
| Tài liệu | `.venv/bin/python scripts/check_docs_consistency.py` | Kiểm tra nhất quán docs |
| Release | `scripts/verify_release.py` | Bundle bằng chứng CP5 |

Mỗi hạng mục hoàn thành cần có test, bằng chứng, cập nhật trạng thái và báo cáo
hoàn thành bằng tiếng Anh. Route `GET .../top-down` hiện **chưa có test backend**.

## 14. Hiện trạng theo checkpoint

| CP | Trạng thái | Ghi chú |
|---|---|---|
| CP0 | `PARTIAL` | Nền Python/esmini đã có; cần báo cáo phase |
| CP1 | `PARTIAL/CORRIDOR-EXTERNAL-VERIFIED` | Corridor 40 m đã kiểm chứng cấu trúc/runtime; road-match `20/143 = 13.99%` |
| CP2 | `CP2-A-COMPLETE/CARLA-UNVERIFIED` | Planner và interpreter XOSC đã có; CARLA post-MVP |
| CP3 | `PARTIAL/IMPLEMENTED` | ADE/FDE, gate, aggregate đa cảnh đã nối; chỉ mục cảnh chưa duyệt |
| CP4 | `PARTIAL/EVIDENCE-CLOSED` | G1–G7 tích hợp; chính sách G6/G7 còn mở |
| CP5 | `PARTIAL/RELEASE-EVIDENCE` | Lockfile, manifest, bundle; chờ owner ký |
| CP6 | `OPEN` | Câu hỏi nghiên cứu và bằng chứng bài báo |

Thứ tự việc tiếp theo: tích hợp source-state devkit Phase 2 → map/LiDAR native →
đánh giá prediction → tích hợp Tier 1 → đóng CP1/CP3/CP4/CP5 → workspace 2D/3D
đầy đủ → bằng chứng CP6.

## 15. Rủi ro, giới hạn và ranh giới tuyên bố

### 15.1 Rủi ro

| # | Rủi ro | Mức | Giảm thiểu |
|---|---|---|---|
| R1 | Map `.xodr` sai kết nối/hình học | Cao | Corridor cục bộ trước; đo road-match; không cắt hình học để ép khớp |
| R2 | Road-match thấp (13.99%) do độ lệch ngang chưa giải thích | Cao | Đã loại trừ 3 giả thuyết bằng đo; đang chẩn đoán tiếp |
| R3 | Chỉ số tự kiểm vòng tròn | Trung bình | Ground truth là keyframe thô; biến thể đo qua Tier 0 |
| R4 | WASM lệch native | Trung bình | Ràng buộc parity dt `0.01`, Worker giữ đồng hồ; chỉ diagnostic |
| R5 | Recipe mất khi restart, batch đồng bộ | Thấp | Ghi rõ giới hạn; cần cap concurrency trước khi public rộng |

### 15.2 Giới hạn đã biết

- Recipe chỉ lưu in-process; batch tạo đồng bộ; danh sách source-scene chưa phân trang.
- Control esmini native chưa có do ABI; khung cảm biến sau chỉnh sửa là `unsupported`.
- Behavior, Validate, Replay trên toolbar bị tắt có chủ đích và có nhãn unavailable.

### 15.3 Không được tuyên bố (DEC-018)

- Không claim độ chính xác bản đồ (G3 chưa có ứng viên nào đạt).
- Không claim an toàn/TTC (G6 luôn fail do cài đặt).
- Không dùng `0.0411 m` để nói mô phỏng "chính xác X%".
- Không lấy số liệu từ preview WASM hay hình ảnh trình duyệt.
- Không báo capability unavailable như kết quả thành công.

## 16. Tài liệu nguồn

| Chủ đề | Tài liệu |
|---|---|
| Phạm vi dài hạn | `MVP&ProjectSummary.md` |
| Trạng thái hiện hành | `docs/current/project-status.md` |
| Quyết định | `docs/current/decisions.md` |
| Hợp đồng kỹ thuật | `docs/current/technical-contracts.md` |
| Kiến trúc | `docs/architecture/system-overview.md`, `boundary-map.md` |
| API, artifact | `docs/contracts/api-surface.md`, `canonical-artifacts.md` |
| Phân hệ | `docs/subsystems/*/README.md` |
| Đặc tả UI | `docs/current/ui-mvp-flow-spec.md` |
| Bảo mật & triển khai | `docs/guides/security-deployment.md` |
| Bằng chứng | `docs/current/evidence-index.md` |
