# Kiến trúc

## 1. Nguyên tắc thiết kế

- Tách việc diễn giải dữ liệu ghi nhận khỏi export đặc thù simulator.
- Giữ provenance và tham số sinh xác định trong mọi artifact.
- Báo lỗi scenario không hợp lý rõ ràng, không tự sửa trajectory một cách im lặng.
- Mỗi quyết định validation phải review được.
- Bắt đầu bằng một process với module boundary rõ ràng, không dùng microservice.

## 2. Pipeline

```text
nuScenes metadata
  -> ingestion và trích xuất event window
  -> canonical Scenario
  -> biến đổi toạ độ local theo hướng đường
  -> OpenSCENARIO exporter
  -> esmini runner
  -> replay trace và metrics
  -> generator biến thể có ràng buộc
  -> validation, xếp hạng, export/report
```

Mọi artifact phải nêu source frame, local reconstruction frame và simulator frame. Coordinate transform cần khả năng đảo chiều khi phù hợp, đồng thời có unit test bằng điểm đã biết.

## 3. Canonical contract

`src/real2scenario/models.py` là contract chung cho mọi bước pipeline. Module này không được import nuScenes, esmini, CARLA, UI hoặc XML library.

| Kiểu | Field bắt buộc | Invariant |
| --- | --- | --- |
| `State` | time, x, y, yaw, speed | Thời gian hữu hạn, không âm; giá trị dùng SI. |
| `Actor` | ID, type, trajectory | ID actor duy nhất trong scenario; timestamp tăng nghiêm ngặt. |
| `Scenario` | ID, duration, ego ID, actors, provenance | Ego tồn tại; duration bao phủ mọi state. |
| `VariantConfig` | speed multiplier, gap delta, timing offset, seed | Input serializable và bắt buộc lưu cùng output. |

## 4. Ranh giới module

```text
src/real2scenario/
  models.py             Dataclass chuẩn và validation
  serialization.py      JSON artifact có version và provenance validation
  ingestion/            Adapter nuScenes và event mining
  map/                  Coordinate transform và road template
  export/               Sinh OpenSCENARIO XML
  simulation/           esmini runner và parse trace
  generation/           Chiến lược perturbation có kiểm soát
  validation/           Feasibility, replay metrics, ranking
  api/                  Ranh giới FastAPI cho local M4 và platform sau M4
```

Quy tắc:

- `ingestion` tạo canonical object, không viết XML.
- `export` chỉ đọc canonical object, không đọc file nuScenes.
- `simulation` chạy/đọc artifact simulator, không quyết định scenario có hiếm hay không.
- `validation` ghi structured data cho mọi lý do reject.
- UI/API chỉ gọi orchestration; không chứa business rule.

R2S-102 ingestion đọc nuScenes metadata và tạo `Scenario` trong
`nuscenes_global` frame. Nó nhận source window va instance token rõ ràng; việc
chọn actor theo interaction thuộc R2S-103, còn source-to-local road-aligned
transform thuộc R2S-201.

`serialization.py` ghi envelope `schema_version` và `artifact_type`. Artifact
baseline lưu canonical scenario; artifact variant lưu thêm `parent_scenario_id`
và `variant_config` gồm speed multiplier, gap delta, timing offset và seed.
Mọi artifact yêu cầu provenance gồm dataset/version, source scene/window,
coordinate-transform version, map reconstruction mode/version và generator version.

## 5. Bố cục artifact

```text
scenarios/
  baseline/<scenario-id>/
    scenario.json
    baseline.xosc
  generated/<parent-id>/<variant-id>/
    scenario.json
    scenario.xosc
    config.json
    replay.csv
    report.json
maps/
  highway.xodr
  intersection.xodr
reports/
```

Generated file bị ignore mặc định. Có thể commit fixture nhỏ đã được curate trong `tests/fixtures/` nếu giấy phép cho phép.

## 6. Chiến lược simulator

esmini là backend MVP vì nhẹ, hỗ trợ OpenSCENARIO/OpenDRIVE trực tiếp và phù hợp batch headless. Các map đầu tiên là OpenDRIVE template được curate. Một segment nuScenes được đưa về local road-aligned frame và replay trên template được hỗ trợ gần nhất.

Đây là xấp xỉ. Report phải lưu `map_reconstruction_mode` và phiên bản map/template; không gọi đây là chuyển đổi trực tiếp từ nuScenes map.

CARLA là adapter bổ sung sau khi canonical scenario, exporter, metrics và review artifact đã ổn định. CARLA phải consume canonical model chung, không trở thành data model của project.

## 7. Validity và ranking

Mỗi variant được đánh giá theo thứ tự:

1. Schema validity: ID đầy đủ, giá trị hữu hạn, timestamp tăng đơn điệu.
2. Kinematic validity: acceleration, deceleration, jerk và yaw-rate trong giới hạn cấu hình.
3. Road validity: vị trí nằm trong lane/drivable corridor khi map mode hỗ trợ.
4. Simulator validity: XML parse được và esmini chạy hoàn tất.
5. Feature chất lượng/rủi ro: TTC, khoảng cách, độ lớn biến đổi, replay error.

Report phải giữ mọi kết quả check; không rút scenario bị reject thành một boolean không có nguyên nhân.

```text
score = novelty + risk_signal + replay_quality - feasibility_penalty
```

Trọng số là cấu hình có version. Điểm cao không thể ghi đè validation thất bại.

## 8. Yêu cầu vận hành

- Python 3.11 trở lên.
- Path binary bên ngoài đến từ config hoặc environment variable, không hard-code path cá nhân.
- Mỗi batch ghi manifest gồm command version, source IDs, map version, generator settings và timestamp.
- CI phải chạy được test suite khi không có full nuScenes dataset hoặc esmini binary. Simulator integration test được đánh dấu riêng.
