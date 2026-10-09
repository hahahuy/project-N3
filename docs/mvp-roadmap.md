# Roadmap MVP và tickets

Đây là execution ledger. Mỗi ticket cần một owner, pull request, bằng chứng automated test khi phù hợp, và bằng chứng review nêu tại checkpoint. Ticket chưa hoàn thành chỉ vì code đã tồn tại.

## Tóm tắt milestone

| Milestone | Kết quả | Cổng review |
| --- | --- | --- |
| M0 | Repository tái lập và canonical contract | Review contract |
| M1 | Có thể inspect và trích xuất recorded segment | Review data |
| M2 | Baseline OpenSCENARIO replay trong esmini | Review replay |
| M3 | Sinh và validate biến thể có ràng buộc | Review generation |
| M4 | Hoàn thiện demo UI và release evidence | Review demo |

## M0: Foundation và contract

### R2S-001: Khởi tạo repository

- Deliverable: `pyproject.toml`, package layout, test layout, `.gitignore`, README.
- Acceptance criteria: `pip install -e ".[dev]"` và `pytest` chạy trong môi trường sạch.
- Evidence: output CI/local command và `git status` sạch sau test.
- Dependencies: không có.

### R2S-002: Canonical scenario schema

- Deliverable: model `State`, `Actor`, `Scenario`, provenance và variant configuration.
- Acceptance criteria: đơn vị SI có tài liệu; actor ID duy nhất; ego tồn tại; timestamp tăng nghiêm ngặt; input invalid ném exception hữu ích.
- Evidence: unit test cho valid scenario và từng invariant lỗi chính.
- Dependencies: R2S-001.

### R2S-003: Quy ước artifact và provenance

- Deliverable: format ID scenario/variant và JSON manifest contract.
- Acceptance criteria: mọi artifact sinh ra có source dataset/version, source scene/window, map mode/version, generator version, seed/config.
- Evidence: JSON artifact mẫu commit vào `tests/fixtures/` mà không chứa dataset content bị hạn chế.
- Dependencies: R2S-002.

### Checkpoint M0: Review contract

- [x] Package cài được bằng lệnh đã ghi.
- [x] Không có dataset path, local binary path hoặc secret bị hard-code.
- [x] Canonical schema có unit test cho mọi invariant.
- [x] Unit và coordinate-frame field rõ ràng.
- [x] Reviewer xác định được source và config của mọi artifact từ manifest.
- [x] `models.py` không phụ thuộc simulator/UI.

## M1: Ingestion và scenario mining

### R2S-100: Onboarding nuScenes và data inventory

- Deliverable: data inventory hoàn chỉnh và walkthrough/notebook ngắn về scene, sample, sample data, annotation, ego pose, calibration, map record.
- Acceptance criteria: mọi thành viên giải thích được file nào cung cấp trajectory, file nào là raw sensor/panoptic label, và vì sao subset panoptic hiện tại không thể tự tái dựng scenario.
- Evidence: onboarding note commit theo `docs/nuscenes-and-simulation-guide.md`, screenshot một rendering từ official devkit, source segment ID đã chọn.
- Dependencies: R2S-001.

### R2S-101: Dataset preflight cho nuScenes

- Deliverable: command kiểm tra metadata bắt buộc và báo missing file có hướng dẫn xử lý.
- Acceptance criteria: kiểm tra scene, sample, sample_data, sample_annotation, ego_pose, calibrated_sensor và map theo mode được chọn.
- Evidence: test dùng temporary directory fixture cho metadata layout đầy đủ và thiếu.
- Dependencies: R2S-001.

### R2S-102: Trích xuất trajectory ego và actor

- Deliverable: adapter đổi một source window cấu hình được thành canonical `Scenario`.
- Acceptance criteria: trả về ego và actor được track với time, position, yaw, speed, dimensions và source token.
- Evidence: một synthetic fixture test và một real-data smoke run có tài liệu.
- Dependencies: R2S-002, R2S-101.

### R2S-103: Interaction window và chọn actor

- Deliverable: selector cấu hình được dùng distance/TTC và manual override.
- Acceptance criteria: actor được chọn và lý do reject được ghi vào provenance; hỗ trợ 1-3 non-ego actor.
- Evidence: test threshold chọn, deterministic tie-break và manual selection.
- Dependencies: R2S-102.

### R2S-104: Top-down source visualizer

- Deliverable: CLI plot hoặc notebook phát extracted trajectory trong local frame.
- Acceptance criteria: reviewer scrub/phát được segment 8-20 giây, phân biệt ego và từng actor.
- Evidence: screenshot/video và command trong docs.
- Dependencies: R2S-102.

### Checkpoint M1: Review data

- [x] Có trajectory data bắt buộc; không coi panoptic mask là track.
- [x] Data inventory của team nêu raw sensor và metadata file có sẵn cục bộ.
- [x] Một source segment được ghi rõ có ego và ít nhất một actor tương tác.
- [x] State timestamp đơn điệu và tính bằng giây.
- [x] Coordinate frame và origin được hiển thị/ghi tài liệu.
- [x] Lý do chọn actor nằm trong scenario artifact.
- [x] Reviewer tái tạo extraction bằng một command/config.

## M2: Tái dựng baseline và replay

### R2S-201: Local coordinate transform

- Deliverable: source-to-local road-aligned transform và metadata transform.
- Acceptance criteria: round-trip error trên test point nhỏ hơn numerical tolerance cấu hình; axes/unit có tài liệu.
- Evidence: unit test gồm yaw wrapping và visual overlay.
- Dependencies: R2S-102.

### R2S-202: OpenDRIVE template registry

- Deliverable: `.xodr` template được hỗ trợ có version và selector contract.
- Acceptance criteria: source scenario lưu lý do chọn template; topology không hỗ trợ bị reject, không map im lặng.
- Evidence: registry unit test và sơ đồ template để review.
- Dependencies: R2S-201.

### R2S-203: OpenSCENARIO baseline exporter

- Deliverable: exporter canonical scenario sang `.xosc` cho ego và 1-3 actor.
- Acceptance criteria: XML validate cấu trúc; entity name ổn định; toàn bộ trajectory timing rõ ràng; output không chứa path theo máy người dùng.
- Evidence: XML parsing test và golden-file diff test.
- Dependencies: R2S-002, R2S-202.

### R2S-204: esmini runner và trace parser

- Deliverable: subprocess runner có cấu hình và normalized replay trace.
- Acceptance criteria: bắt timeout/error output; lưu exit status và esmini version trong report; runner mock được trong unit test.
- Evidence: unit test với fake executable và integration test được đánh dấu tuỳ chọn.
- Dependencies: R2S-203.

### R2S-205: Replay fidelity metrics

- Deliverable: timestamp alignment, position RMSE, final displacement error, heading MAE và speed MAE.
- Acceptance criteria: input/output metric có unit; trace rỗng hoặc mismatch fail rõ ràng; known numeric example pass.
- Evidence: unit test với expected metric tính tay.
- Dependencies: R2S-204.

### Checkpoint M2: Review replay

- [x] Ít nhất một baseline `.xosc` khởi động và hoàn tất trong esmini.
- [x] Original/replay trajectory được overlay trong một artifact.
- [x] Metric nêu unit, phương pháp timestamp alignment và sample count.
- [x] Map reconstruction được gắn nhãn local/template approximation.
- [x] Simulator execution fail giữ stderr/exit status trong report.
- [x] Reviewer tái tạo baseline XML và replay trace từ source config.

## M3: Sinh biến thể, validation và ranking

### R2S-301: Parameterized perturbations

- Deliverable: biến đổi speed multiplier, initial longitudinal gap và timing offset.
- Acceptance criteria: transformation không mutate parent scenario; mọi child lưu parameter value đầy đủ và seed.
- Evidence: test immutability, deterministic output và trajectory offset mong đợi.
- Dependencies: R2S-002, R2S-203.

### R2S-302: Batch generator

- Deliverable: batch command grid/random có manifest và variant ID ổn định.
- Acceptance criteria: config/seed cố định sinh cùng ID và configuration theo cùng thứ tự.
- Evidence: deterministic batch test và manifest mẫu.
- Dependencies: R2S-301.

### R2S-303: Feasibility validation

- Deliverable: kiểm tra kinematic và road boundary được hỗ trợ, có structured rejection reason.
- Acceptance criteria: threshold acceleration, deceleration, jerk, yaw-rate và road boundary đến từ config.
- Evidence: boundary-value test pass tại ngưỡng, fail khi vượt ngưỡng.
- Dependencies: R2S-201, R2S-301.

### R2S-304: Risk feature và ranking

- Deliverable: minimum distance, TTC, novelty feature và breakdown score có version.
- Acceptance criteria: validity fail không được rank là valid; collision/near-miss không được suy luận khi chưa nêu definition.
- Evidence: test TTC edge case và score breakdown snapshot.
- Dependencies: R2S-303, R2S-205.

### R2S-305: Batch report exporter

- Deliverable: report từng variant và aggregate CSV/JSON summary.
- Acceptance criteria: count khớp chính xác: generated = valid + invalid + simulator-failed; mỗi result link mọi artifact.
- Evidence: reconciliation test và batch report mẫu.
- Dependencies: R2S-302, R2S-303, R2S-304.

### Checkpoint M3: Review generation

- [x] Batch ít nhất 20 variant sinh từ baseline cố định.
- [x] Rerun seed/config tái tạo ID và trajectory.
- [x] Report tách invalid, simulator-failed và valid case.
- [x] Mọi reject có một hoặc nhiều structured reason.
- [x] Kinematic/map threshold là config có version, không phải magic number.
- [x] Score component hiển thị rõ; không đánh đồng “rare” với “safe”.

R2S-304 and R2S-305 evidence: `docs/r2s-304-ranking-evidence.md` and
`docs/r2s-305-reporting-evidence.md`. The 20-variant baseline batch evidence is
in `docs/r2s-306-20-variant-batch-evidence.md`.

## M4: Demo và release

### R2S-401: MVP dashboard

- Deliverable: browser, trajectory playback, control, result table và export action.
- Acceptance criteria: demo flow trong `product-spec.md` chạy không cần sửa file trực tiếp hay terminal sau khi khởi động.
- Evidence: video demo 3 phút và UI smoke-test checklist.
- Dependencies: R2S-104, R2S-205, R2S-305.

### R2S-402: Curate demo scenario

- Deliverable: ba source segment có nhãn: lead braking cộng hai interaction hỗ trợ khác.
- Acceptance criteria: mỗi segment có baseline replay, batch 20 variant và một valid variant phù hợp trình bày.
- Evidence: curation index với artifact path và metric.
- Dependencies: R2S-305.

### R2S-403: Release và reproducibility pack

- Deliverable: setup guide, configuration example, known limitation, demo script, evidence bundle.
- Acceptance criteria: reviewer mới setup project và tái tạo một curated batch từ instruction.
- Evidence: ghi chú verification trên clean machine.
- Dependencies: R2S-401, R2S-402.

### Checkpoint M4: Review demo

- [ ] Walkthrough chọn, replay, biến đổi, validate, rank và export một scenario.
- [ ] Dashboard phân biệt rõ recorded, replayed và generated path.
- [ ] Ít nhất ba curated source scenario có evidence đầy đủ.
- [ ] Aggregate count khớp report từng variant.
- [ ] Limitation và licensing hiển thị trong docs/demo.
- [ ] Reviewer đi theo script được mà không cần manual step không ghi tài liệu.

## Nhịp review đề xuất

- Review M0 trước khi tải hoặc tích hợp full dataset.
- Review M1 trước khi chốt simulator map representation.
- Review M2 trước khi xây UI hoặc batch generator.
- Review M3 trước khi mô tả project là rare-scenario generation.
- Review M4 với clean checkout và demo script chính xác.
