# R2S-100: Onboarding nuScenes va data inventory

## Dataset da kiem tra

- Dataset: nuScenes `v1.0-mini` full release.
- Local-only root: `data/v1.0-mini/`.
- Kich thuoc tai thoi diem kiem tra: 5.1 GB, 31,225 files.
- License: da giu tai `data/LICENSE`; raw dataset, sensor payload va rendering
  khong duoc commit vao repository.
- Devkit environment: Python 3.11, `nuscenes-devkit==1.2.0`, Matplotlib 3.11.2.

## Inventory

Chay thanh cong:

```bash
source .venv/bin/activate
real2scenario-preflight --root data/v1.0-mini --version v1.0-mini --map-mode expansion
real2scenario-devkit --root data/v1.0-mini --version v1.0-mini inventory \
  --output /tmp/nuscenes-mini-inventory.json
```

| Hang muc | Co? | Path/version | Ghi chu reviewer |
| --- | --- | --- | --- |
| Core metadata tables | Co | `data/v1.0-mini/v1.0-mini`, `v1.0-mini` | 10 scene, 404 sample, 31,206 sample_data |
| Map expansion data | Co | `maps/` va `v1.0-mini/map.json` | 4 map record, cac file raster duoc manifest tham chieu |
| Front-camera frames | Co | `samples/CAM_FRONT/` | Raw `.jpg` co san |
| Top/primary LiDAR frames | Co | `samples/LIDAR_TOP/` | Raw `.bin` co san |
| Sample annotations va instances | Co | `sample_annotation.json`, `instance.json` | 18,538 annotation, 911 instance |
| Ego poses va calibration | Co | `ego_pose.json`, `calibrated_sensor.json` | 31,206 pose, 120 calibration |
| Panoptic labels | Khong trong full-mini root | Can them panoptic expansion tuong thich neu can semantic review | Khong can de extract trajectory |
| NuScenes devkit version | Co | `.venv`, `nuscenes-devkit==1.2.0` | Import va load da smoke-test |
| Da review license/attribution | Co | `data/LICENSE` | Khong commit data/artifact dan xuat co noi dung raw |

## Source segment va rendering

Source segment dau tien da chon de onboarding:

- Scene name: `scene-0061`.
- Scene token: `cc8c0bf57f984915a77078b10eb33198`.
- First sample token: `ca9a282c9e77460f8360f564131a8af5`.
- Scene co 39 keyframe.
- Log token: `7e25a2c8ea1f41c5b0da1e69ecfa71a2`.

Rendering da thanh cong voi official devkit, output local-only `/tmp/nuscenes-mini-scene-0.png`
(2,998,543 bytes):

```bash
real2scenario-devkit --root data/v1.0-mini --version v1.0-mini render \
  --scene-index 0 --output /tmp/nuscenes-mini-scene-0.png
```

## Hieu biet can dung cho ingestion

- `scene.json` chon source segment va first/last sample token.
- `sample.json` la timeline keyframe; `sample_data.json` noi sample voi sensor
  datum va `ego_pose`.
- `sample_annotation.json` va `instance.json` tao actor track; `category.json`
  map source category sang actor type.
- `ego_pose.json` tao ego trajectory global; `calibrated_sensor.json` can thiet
  khi dien giai sensor frame.
- Camera `.jpg`, LiDAR `.bin`, radar `.pcd` la raw sensor data de review, khong
  phai source trajectory truc tiep.
- Panoptic mask chi la semantic/instance label cua sensor; khong thay the
  annotation/instance track hay ego pose.
- MVP se extract recorded trajectory trong source global frame truoc, sau do
  R2S-201 moi chuyen sang local road-aligned frame co version.
