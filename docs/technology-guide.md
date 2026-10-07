# Hướng dẫn công nghệ và cách sử dụng

## 1. Bản đồ công nghệ

| Công nghệ | Phase | Trách nhiệm | Bắt buộc cho MVP |
| --- | --- | --- | --- |
| Python 3.11+ | M0-M4 | Core pipeline, data model, command, test | Có |
| `pytest` | M0-M4 | Chạy unit/integration test | Có |
| `numpy`, `pandas`, `scipy` | M1-M3 | Xử lý trajectory, nội suy, metric số | Có khi bắt đầu implement |
| `nuscenes-devkit` | M1 | Đọc metadata, track, pose và map nuScenes | Có |
| OpenSCENARIO XML | M2-M4 | Scenario artifact di động | Có |
| OpenDRIVE `.xodr` | M2-M4 | Road template cho backend replay | Có |
| esmini | M2-M4 | Replay OpenSCENARIO headless, batch validation | Có |
| Streamlit, Plotly | M4 | Demo UI và top-down playback nhanh | Có cho UI demo |
| FastAPI | Sau MVP | API boundary cho multi-user/React | Không |
| CARLA | Sau MVP | 3D, sensor simulation, closed-loop test | Không |
| Docker | Sau MVP | Deployment/CI tái lập sau khi native dependency ổn định | Không |

Chỉ dùng công cụ nhỏ nhất chứng minh checkpoint kế tiếp. Cài CARLA, Docker, database và React trước M2 tạo chi phí vận hành nhưng chưa chứng minh được data-to-scenario pipeline.

## 2. Môi trường Python cục bộ

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

Kết quả mong đợi ở M0 là schema test suite pass. Giai đoạn này không cần full nuScenes dataset, OpenDRIVE map hay simulator binary.

Khi bắt đầu M1, thêm dependency được pin version vào `pyproject.toml`, không phụ thuộc local install không được ghi nhận:

```text
numpy
pandas
scipy
nuscenes-devkit
```

Chỉ thêm `lxml` nếu XML builder trong standard library không đủ. Exporter phải deterministic bất kể XML library.

## 3. Setup dữ liệu nuScenes

Thư mục đã track `data/nuScenes-panoptic-v1.0-mini` chỉ có panoptic material, không có object/ego trajectory cần cho project. Trước `R2S-102`, tải nuScenes mini theo quy trình chính thức và tuân thủ license.

Đọc [hướng dẫn nuScenes và mô phỏng](nuscenes-and-simulation-guide.md) trước M1. Guide giải thích bảng dữ liệu, coordinate frame, công cụ visualization chính thức, file cục bộ cần có, và khác biệt giữa trajectory replay với sensor-level replication.

Loader cần tối thiểu:

```text
scene.json
sample.json
sample_data.json
sample_annotation.json
ego_pose.json
calibrated_sensor.json
log.json
```

```bash
export NUSCENES_ROOT="$HOME/datasets/nuscenes"
export NUSCENES_VERSION="v1.0-mini"
```

Trích xuất có nhận biết lane cần thêm nuScenes map data. R2S-101 cung cấp
preflight không cần `nuscenes-devkit`; command chỉ kiểm tra filesystem và JSON
metadata, không đọc hay phân phối raw sensor data:

```bash
real2scenario-preflight --root "$NUSCENES_ROOT" --version "$NUSCENES_VERSION"
```

Mặc định command kiểm tra `v1.0-mini/map.json` cùng từng map file mà manifest
tham chiếu trong `$NUSCENES_ROOT/maps`, đủ cho map-aware extraction ở data stage.
Khi team chỉ kiểm tra metadata trước khi map expansion được cấp phép/tải về, dùng
explicit mode sau; kết quả `READY` trong mode này chưa đủ điều kiện cho
road-aware extraction:

```bash
real2scenario-preflight \
  --root "$NUSCENES_ROOT" \
  --version "$NUSCENES_VERSION" \
  --map-mode none
```

Command exit `0` khi sẵn sàng và `1` khi thiếu hoặc hỏng input; mỗi lỗi nêu path
và bước xử lý. Required tables gồm `scene`, `sample`, `sample_data`,
`sample_annotation`, `instance`, `ego_pose`, `calibrated_sensor`, `sensor`,
`category`, và `log`.

Môi trường project đã pin `nuscenes-devkit==1.2.0` và Matplotlib trong optional
extra `devkit`. Dùng Python 3.11 cho devkit environment hiện tại:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,devkit]"
```

Sau khi complete licensed mini release có ở `$NUSCENES_ROOT`, tạo inventory
reviewable và render keyframe đầu của scene đầu tiên:

```bash
real2scenario-devkit \
  --root "$NUSCENES_ROOT" \
  --version "$NUSCENES_VERSION" \
  inventory \
  --output /tmp/nuscenes-inventory.json

real2scenario-devkit \
  --root "$NUSCENES_ROOT" \
  --version "$NUSCENES_VERSION" \
  render \
  --scene-index 0 \
  --output /tmp/nuscenes-scene-0.png
```

Để render một keyframe đã chọn thay vì scene đầu, thay `--scene-index 0` bằng
`--sample-token <token>`. `inventory` nêu count từng table và token scene/sample
để ghi evidence R2S-100. `render` cần raw sensor file ngoài metadata JSON.

Sau khi R2S-102 extract source segment thanh canonical artifact, render top-down
path va mo viewer scrub/play bang command sau:

```bash
real2scenario-visualize /tmp/scenario.json --output /tmp/source-top-down.png
real2scenario-visualize /tmp/scenario.json --show
```

`--show` mo control time scrubber va Play/Pause; ego dung mau do, moi actor dung
mau rieng. `--output` tao PNG headless de reviewer luu evidence. Artifact JSON
phai la baseline/variant artifact da qua serialization validation, khong phai
raw nuScenes metadata.

- Không hard-code home directory trong source.
- Không commit full dataset, credential hay raw data không được phép phân phối.
- Lưu source scene token, sample range, dataset version và extraction version trong từng canonical scenario.
- Giữ yêu cầu attribution và non-commercial/share-alike từ `data/LICENSE` với artifact dẫn xuất khi cần.

## 4. OpenSCENARIO và OpenDRIVE

OpenSCENARIO (`.xosc`) mô tả entity, trạng thái khởi tạo, action, trajectory và trigger. OpenDRIVE (`.xodr`) mô tả road network. MVP dùng cả hai vì trajectory cần road context để replay và validate ràng buộc lane/drivable area.

Ở M2 chỉ dùng một tập template có version, được curate thủ công:

```text
maps/
  highway-v1.xodr
  intersection-v1.xodr
```

Pipeline bắt buộc lưu:

```text
source coordinate frame -> local road-aligned frame -> simulator frame
map reconstruction mode -> map template ID/version
```

Segment không khớp template được hỗ trợ phải bị reject hoặc đánh dấu unsupported ở M2, không được biến dạng im lặng.

## 5. Setup và dùng esmini

esmini là execution backend cho MVP. Cài bản esmini đã được team kiểm tra từ nguồn chính thức, sau đó cấu hình executable mà không commit local path.

```bash
export ESMINI_BIN="/absolute/path/to/esmini"
"$ESMINI_BIN" --help
```

`R2S-204` sẽ bọc command line. Contract mục tiêu:

```bash
real2scenario replay \
  --scenario scenarios/baseline/<scenario-id>/baseline.xosc \
  --map maps/highway-v1.xodr \
  --output scenarios/baseline/<scenario-id>/replay.csv
```

Đây chưa phải CLI đã implement. Runner bắt buộc lưu executable/version, command không chứa secret, timeout, exit code, stdout/stderr, trace location, source scenario và map template ID. Chạy headless cho batch; GUI chỉ dùng inspect thủ công scenario được curate.

## 6. Vì sao esmini là backend MVP

| Tiêu chí | esmini | CARLA | Quyết định MVP |
| --- | --- | --- | --- |
| Mục tiêu gốc | Playback OpenSCENARIO/OpenDRIVE nhẹ | Simulator lái xe 3D đa dụng | Ưu tiên esmini |
| Batch headless | Khởi động nhanh, footprint nhỏ | Server/client nặng, thường cần GPU | Ưu tiên esmini |
| Validate `.xosc` | Thực thi trực tiếp artifact sinh ra | Không phải workflow cốt lõi của MVP | Ưu tiên esmini |
| Regression test | Dễ chạy deterministic hơn | Nhiều nguồn runtime variance hơn | Ưu tiên esmini |
| 3D và sensor | Hạn chế | Camera/LiDAR/radar/weather mạnh | Dùng CARLA sau |
| Closed-loop autonomy | Không phải mục tiêu | Phù hợp | Dùng CARLA sau |

Câu hỏi MVP là: “Có thể tái dựng, replay, đo và biến đổi tương tác đã ghi nhận một cách tái lập không?” esmini trả lời câu hỏi này với độ phức tạp thấp nhất. CARLA sẽ thêm 3D asset, server, version matching client, map import, synchronous tick và ràng buộc GPU trước khi core transformation được kiểm chứng.

Đây là quyết định thứ tự triển khai, không phải khẳng định esmini tốt hơn CARLA ở mọi trường hợp. Canonical `Scenario` được thiết kế để có thể thêm CARLA sau này.

## 7. Khi nào thêm CARLA

Chỉ thêm CARLA adapter sau M3 khi có nhu cầu thực:

- Demo cần 3D thay vì top-down replay.
- Cần camera, LiDAR, radar, weather, lighting hoặc occlusion.
- Autonomy stack phải điều khiển ego ở chế độ closed loop.
- Scenario cần đánh giá perception/planning/control thay vì trajectory open-loop cố định.
- Team có môi trường tái lập với CARLA server/client version được hỗ trợ và đủ GPU.

CARLA là milestone riêng, không thay thế baseline esmini:

```text
Canonical Scenario
  -> CARLA adapter
  -> CARLA world/entities/actions
  -> CARLA replay trace
  -> cùng metric và report contract
```

Trước khi implement, tạo ticket cho ranh giới chuyển đổi coordinate/map. CARLA map, asset semantic, actor blueprint và behavior API không tương đương `.xosc`; hành vi không hỗ trợ phải fail rõ ràng, không xấp xỉ im lặng.

## 8. Metrics, validation, UI và test

Metric chỉ tính sau khi source/replay trace được căn chỉnh vào common time grid có tài liệu:

| Metric | Đơn vị | Diễn giải |
| --- | --- | --- |
| Position RMSE | m | Độ lệch phẳng điển hình khi replay. |
| Final displacement error | m | Drift ở cuối window. |
| Heading MAE | độ hoặc radian, phải nêu rõ | Sai khác hướng. |
| Speed MAE | m/s | Sai khác động học. |
| Minimum TTC | s | Tín hiệu rủi ro, không bảo đảm an toàn. |
| Minimum distance | m | Khoảng cách actor gần nhất. |

Validator chạy theo thứ tự schema, kinematic, road, simulator rồi risk. Scenario fail validation bắt buộc vẫn là invalid dù TTC thú vị hoặc novelty score cao.

Ở M4 dùng Streamlit để chứng minh end-to-end flow trước khi duy trì frontend/API riêng. Dashboard cần: chọn source, xem timeline, xem overlay/replay metric, đặt speed/gap/timing, generate/validate batch, lọc validity trước score, và export `.xosc`/JSON/trace/report.

Chỉ dùng FastAPI + React khi cần concurrent user, queued job dài, deployment riêng hoặc tương tác vượt giới hạn Streamlit. Điều này không được thay đổi canonical model/report contract.

| Mức test | Chạy không cần | Ví dụ |
| --- | --- | --- |
| Unit | Dataset và simulator | Schema, transform, TTC, metric, deterministic ID. |
| Fixture | Full dataset và simulator | Parse fixture canonical/trace/XML đã làm sạch. |
| Integration | External binary tuỳ chọn | Export `.xosc`, chạy esmini, parse replay trace. |
| Demo smoke test | Tự động hoá toàn bộ | Walkthrough UI curate, kiểm tra artifact export. |

Lỗi external integration phải lưu đủ context để tái lập: source scenario ID, map version, command, config/seed, tool version, exit code và log.
