# Hướng dẫn nuScenes và mô phỏng

## 1. Mục đích

Guide này tạo shared mental model cho team trước khi implement ingestion hoặc simulation. Nó trả lời:

1. nuScenes là gì và file nào quan trọng với project?
2. Xem image, LiDAR, map, box, track và panoptic label bằng cách nào?
3. “Replicate” tương tác nuScenes bằng esmini hoặc CARLA nghĩa là gì?
4. Phần nào tái tạo được trung thực, phần nào bắt buộc ghi là xấp xỉ?

Đọc guide này trước `R2S-100` và `R2S-101`.

## 2. nuScenes là gì

nuScenes là dataset lái xe tự hành được ghi nhận. Một phiên ghi hình chia thành các scene; mỗi scene có sensor measurement liên kết thời gian, ego pose, object annotation và metadata map/log. Bản mini là subset phục vụ development; bản đầy đủ có nhiều scene hơn.

Trong project này, nuScenes là nguồn của tương tác thực tế, không phải simulator. Pipeline trích xuất chuyển động và scene context quan sát được, biểu diễn chúng ở canonical format, rồi tái dựng test tương đương trong simulator.

```text
scene
  -> sample theo thứ tự (keyframe)
     -> sample_data cho mỗi camera/LiDAR/radar sensor
     -> sample_annotation cho box 3D object được track
     -> ego_pose cho pose ego vehicle
     -> calibrated_sensor cho calibration sensor-to-ego
  -> log và map context
```

`sample` là keyframe. `sample_data` nối keyframe với một sensor datum và có thể tạo chuỗi tần số cao hơn. `sample_annotation` chứa box 3D đã gán nhãn cho instance ở keyframe tương ứng. `instance` gom annotation của cùng một vật thể qua thời gian.

## 3. File và ý nghĩa

| Record/file | Nội dung | Lý do Real2Scenario cần |
| --- | --- | --- |
| `scene.json` | Tên scene và sample đầu/cuối | Chọn đoạn lái xe đã ghi nhận. |
| `sample.json` | Timeline keyframe, channel reference | Duyệt interaction window. |
| `sample_data.json` | Sensor file reference, sensor frame liên kết | Tìm camera/LiDAR/radar observation. |
| `sample_annotation.json` | Box 3D, category, instance link | Tái dựng actor track và kích thước. |
| `instance.json` | Danh tính object qua thời gian | Giữ actor ID nhất quán giữa keyframe. |
| `ego_pose.json` | Ego pose trong global coordinate | Tái dựng ego trajectory. |
| `calibrated_sensor.json` | Sensor pose tương đối ego | Project box vào camera/LiDAR, hiểu sensor frame. |
| `sensor.json` | Sensor identity/type/channel | Chọn camera/LiDAR channel cần dùng. |
| `category.json` | Taxonomy object | Map nhãn nguồn sang simulation actor type. |
| `attribute.json` | Thuộc tính moving/parked... | Behavior context tuỳ chọn. |
| Map expansion data | Lane, road, drivable area | Road-aligned extraction, map validity check. |
| Camera image / LiDAR file | Raw observed sensor data | Visual inspection, extension thiên về perception. |
| Panoptic mask / `panoptic.json` | Semantic/instance segmentation label | Kiểm tra semantic; không đủ để tạo trajectory riêng. |

Subset `data/nuScenes-panoptic-v1.0-mini` đang commit chỉ gồm panoptic content và category metadata. Nó **không** có bảng scene/sample/annotation/ego-pose cốt lõi hay raw sensor file. Do đó nó chưa thể cung cấp actor/ego trajectory, camera rendering hoặc scene browsing hoàn chỉnh.

## 4. Coordinate frame

Lỗi coordinate là nguồn lớn gây replay invalid. Luôn lưu tên frame cùng trajectory.

| Frame | Ý nghĩa | Cách dùng |
| --- | --- | --- |
| Global/map | World frame cố định của recorded pose | So sánh ego/actor trong scene. |
| Ego vehicle | Frame gắn với xe ghi nhận | Biểu diễn actor tương đối ego. |
| Sensor | Frame gắn camera/LiDAR/radar | Project annotation 3D vào sensor view. |
| Local road-aligned | Frame do project tạo, đặt origin/hướng tại source window | Export trajectory ổn định sang template map. |
| Simulator | Frame của esmini/OpenDRIVE hoặc CARLA | Chạy scenario tái dựng. |

```text
annotation box trong global frame
  -> inverse ego_pose
  -> ego frame
  -> inverse calibrated_sensor
  -> sensor frame
```

Khi replay, pipeline chọn local origin và heading rồi đổi recorded global position sang local road-aligned frame. Đây là project artifact có version, không phải đổi trục ngầm định.

## 5. Cách inspect nuScenes

### 5.1 Official Python devkit

`nuscenes-devkit` chính thức là công cụ đầu tiên team nên dùng. Nó có table access, `NuScenes` object, visualization helper và map utility. Dùng Jupyter notebook trong onboarding để xem từng representation cùng record tương ứng.

Sau khi đã có licensed nuScenes mini đầy đủ và cài devkit:

```bash
pip install nuscenes-devkit matplotlib
export NUSCENES_ROOT="$HOME/datasets/nuscenes"
export NUSCENES_VERSION="v1.0-mini"
```

```python
import os

from nuscenes.nuscenes import NuScenes

nusc = NuScenes(
    version=os.environ["NUSCENES_VERSION"],
    dataroot=os.environ["NUSCENES_ROOT"],
    verbose=True,
)

nusc.list_scenes()
scene = nusc.scene[0]
first_sample_token = scene["first_sample_token"]
nusc.render_sample(first_sample_token)
```

`render_sample` là view khởi đầu hữu ích nhất: nó overlay annotation trên sensor view hiện có. Lệnh cần raw sensor file tương ứng, không chỉ JSON metadata.

```python
sample = nusc.get("sample", first_sample_token)
nusc.render_sample_data(sample["data"]["CAM_FRONT"])
nusc.render_ego_centric_map(first_sample_token)
```

Tuỳ devkit version và data có sẵn, dùng thêm annotation/point-cloud rendering helper để inspect box và LiDAR. Helper API dành cho khám phá; ingestion production phải đọc, validate metadata gốc.

### 5.2 Có thể xem gì với từng gói tải về

| Dữ liệu cục bộ | Team có thể xem | Chưa có |
| --- | --- | --- |
| Chỉ metadata JSON | Scene graph, timestamp, object metadata, pose | Pixel image, point cloud, panoptic mask rendering. |
| Metadata + camera image | Camera frame có overlay box 3D | LiDAR point, LiDAR panoptic visualization. |
| Metadata + LiDAR | Point cloud, box 3D, map overlay chọn lọc | Camera image nếu không có image. |
| Metadata + panoptic mask | Semantic/instance label khớp sensor gốc | Actor track nếu thiếu annotation/instance. |
| Mini release đầy đủ | Mọi devkit rendering/extraction path hỗ trợ | Tái dựng chính xác world gốc trong simulator khác. |

M1 không cần tải mọi modality. Cần metadata cho ego/object track và ít nhất một modality để visual review. Camera image dễ dùng nhất cho onboarding; LiDAR hữu ích để kiểm tra geometry 3D.

### 5.3 Checklist data inventory

Điền bảng này trước khi code extractor:

| Hạng mục | Có? | Path/version | Ghi chú reviewer |
| --- | --- | --- | --- |
| Core metadata tables |  |  |  |
| Map expansion data |  |  |  |
| Front-camera frames |  |  |  |
| Top/primary LiDAR frames |  |  |  |
| Sample annotations và instances |  |  |  |
| Ego poses và calibration |  |  |  |
| Panoptic labels |  |  |  |
| NuScenes devkit version |  |  |  |
| Đã review license/attribution |  |  |  |

## 6. Từ nuScenes sang canonical scenario

Extractor phải tạo biểu diễn độc lập simulator, không xuất XML trong lúc đọc nuScenes table.

```text
1. Chọn scene và time window.
2. Đọc ego_pose để tạo ego trajectory.
3. Theo annotation/instance để tạo candidate actor track.
4. Chỉ ước lượng speed/heading bằng rule nội suy/vi phân có tài liệu.
5. Chọn 1-3 actor liên quan bằng distance, TTC, lane relation hoặc manual review.
6. Đổi source global coordinate sang local road-aligned frame có tên.
7. Lưu canonical Scenario JSON cùng source token và transform metadata.
```

Mỗi state tối thiểu cần time, position, yaw, speed, actor ID, actor type và dimensions khi biết. Giữ source token gốc để reviewer đi từ scenario sinh ra về nuScenes sample/annotation record.

## 7. “Replicate” nghĩa là gì

Project phải nêu rõ mức fidelity đạt được:

| Mức | Nội dung tái tạo | Trạng thái MVP |
| --- | --- | --- |
| Trajectory replay | Chuyển động ego/actor, timing, relative interaction, road context cơ bản | Bắt buộc. |
| Scene reconstruction | Road geometry, lane, actor shape, traffic furniture, building, lighting | Chỉ xấp xỉ. |
| Sensor replication | Camera/LiDAR/radar observation tương đương data ghi nhận | Sau MVP, cần CARLA/asset/calibration. |

OpenSCENARIO replay thành công nghĩa là tương tác trajectory được tái tạo dưới các giả định đã công bố. Nó không có nghĩa simulator world giống hình ảnh nuScenes gốc, hoặc camera pixel/LiDAR return khớp recorded sensor data.

## 8. Replicate bằng esmini

esmini dùng để validate OpenSCENARIO ở mức trajectory:

```text
nuScenes track
  -> local road-aligned coordinate
  -> chọn OpenDRIVE template hỗ trợ
  -> tạo entity, initial state, trajectory, trigger trong .xosc
  -> esmini replay
  -> normalized replay trace
  -> so sánh source trajectory
```

esmini chứng minh được: `.xosc` chạy được, entity spawn đúng initial state/name, reference trajectory/timing được replay, batch chạy headless tính completion rate/position error/TTC/distance và variant được lọc bằng hành vi chạy được.

MVP không thể dùng esmini để tái tạo trung thực image/LiDAR/weather/building/city asset gốc, exact road topology khi không khớp `.xodr` template, hay phản ứng closed-loop của driving policy không có external controller.

## 9. Replicate bằng CARLA

CARLA hữu ích khi mục tiêu vượt qua trajectory replay:

```text
nuScenes track và map context
  -> local coordinate transform
  -> CARLA town tương thích hoặc custom imported map
  -> chọn vehicle/pedestrian blueprint
  -> spawn actor và áp trajectory/controller behavior
  -> gắn camera/LiDAR/radar sensor nếu cần
  -> chạy synchronous replay, ghi trace/sensor data
  -> so sánh trajectory rồi đến perception output
```

CARLA thêm 3D world, vehicle/pedestrian/road/weather/lighting, synthetic camera-LiDAR-radar-IMU-GNSS-collision output, closed-loop testing cho perception/planning/control và visual demo tốt hơn.

| Quyết định | Chính sách bắt buộc |
| --- | --- |
| Map | Chỉ dùng built-in town có topology phù hợp; nếu không import/build map riêng; không tuyên bố đó là địa điểm nuScenes gốc. |
| Ngoại hình actor | Map nuScenes category/dimension sang CARLA blueprint có tài liệu. |
| Motion | Nêu rõ actor teleport theo reference trajectory, do controller lái, hay do behavior model điều khiển. |
| Vai trò ego | Nêu ego open-loop replay hay do AV stack điều khiển. |
| Đồng bộ | Dùng synchronous tick cố định, lưu tick rate trong report. |
| So sánh sensor | Lưu intrinsic/extrinsic/config; không tuyên bố pixel-level equivalence nếu chưa calibration và validate scene asset. |

Set transform trực tiếp ở open loop có thể khớp position tốt hơn nhưng bỏ qua physical dynamics. Closed-loop phải dùng controller và chấp nhận trajectory error tăng. Hai experiment mode khác nhau, không được trộn metric trong một report.

## 10. esmini so với CARLA trong project này

| Câu hỏi | esmini | CARLA |
| --- | --- | --- |
| Chạy OpenSCENARIO trajectory scenario? | Có, đây là MVP validation path. | Có thể qua adapter/workflow, nhưng không phải MVP contract. |
| Batch nhanh trong headless CI? | Có, được ưu tiên. | Có thể nhưng nặng hơn nhiều. |
| Hiển thị 3D city phong phú? | Hạn chế. | Có. |
| Sinh camera/LiDAR/radar cho AV-stack test? | Không phải MVP path. | Có. |
| Loại bỏ giả định map/coordinate? | Không. | Không; vẫn cần custom map alignment. |
| Khi nào dùng? | M2-M3: export, regression, metric, batch variant. | Sau M3: demo 3D, sensor, closed-loop. |

Kiến trúc là cộng dồn: esmini là cổng OpenSCENARIO nhanh, deterministic; CARLA là backend thứ hai cho experiment fidelity cao hơn. Cả hai consume canonical scenario và emit cùng report shape khi metric so sánh được.

## 11. Bài thực hành onboarding

Hoàn thành trước pull request ingestion đầu tiên:

1. Cài devkit với licensed complete mini dataset.
2. Liệt kê scene và chọn một source scene.
3. Render một keyframe bằng `render_sample`.
4. Tìm ego pose, front-camera sample data và một vehicle annotation theo token.
5. Giải thích annotation đó nối vào `instance` track thế nào.
6. Vẽ global-to-local transform cho exporter tương lai.
7. Ghi rõ interaction có khớp highway/intersection template hỗ trợ không.
8. Nêu phần nào trajectory-replicated, phần nào chỉ xấp xỉ trong esmini/CARLA.

Lưu scene/sample token đã chọn, screenshot và inventory hoàn thành làm evidence cho `R2S-100`.
