# Tài liệu kiểm thử Real2Scenario (N3-09B)

Ngày cập nhật: 17/10/2026 · Bản kiểm thử: `project-N3-main (2)`

## 1. Giới thiệu và phạm vi

Tài liệu này là kế hoạch, bộ ca kiểm thử và báo cáo kết quả kiểm thử cho **Real2Scenario**. Đây là sản phẩm của đề tài N3-09B: chuyển cảnh lái xe thật (nuScenes) thành kịch bản OpenSCENARIO, phát lại bằng esmini và sinh biến thể. Bản được kiểm thử là `project-N3-main (2)`, nhận ngày 17/10/2026.

| Thành phần | Trong phạm vi | Ghi chú |
| --- | --- | --- |
| Lõi `src/real2scenario` (nạp dữ liệu, chọn cảnh, xuất .xosc, phát lại, đo sai số, sinh biến thể, cổng G1–G7) | Có | Trọng tâm, gắn trực tiếp với 2 chỉ số chính thức |
| Backend web `src/r2s_web` (FastAPI) | Có | Kiểm thử API qua TestClient |
| Frontend React `frontend/` | Có | 51 ca Vitest, đã chạy |
| Bộ chuyển đổi CARLA | Một phần | Chỉ test hợp đồng dữ liệu; chưa có máy chạy CARLA |
| Triển khai Docker / nginx / máy chủ demo | Không | Cần quyền vào máy chủ của nhóm |
| Bộ mô phỏng WASM trong trình duyệt | Không | Cần bản build esmini WASM |

Tài liệu dành cho cả nhóm: người viết code dùng mục 4, 6 và 7 để sửa lỗi, người thuyết trình dùng mục 5, 6 và 9 để trả lời câu hỏi về chất lượng.

## 2. Chiến lược và môi trường kiểm thử

Kiểm thử theo 6 mức. Bộ test tự động của nhóm chỉ bao mức 1–3. Mức 4 (kiểm tra chuẩn OpenSCENARIO) và mức 5 (tái hiện lỗi bằng esmini) là phần tài liệu này bổ sung, vì bộ test hiện tại xanh toàn bộ nhưng vẫn để lọt lỗi.

| Mức | Kiểm tra gì | Công cụ | Đã chạy? |
| --- | --- | --- | --- |
| 1. Unit | Từng hàm: toạ độ, độ đo, kiểm tra vật lý, sinh biến thể, xếp hạng | pytest | Có |
| 2. Tích hợp | Xuất .xosc rồi chạy esmini thật, đọc vết lại, tính sai số | pytest + esmini | Có |
| 3. API web | Các endpoint FastAPI qua `TestClient` | pytest + httpx | Có |
| 4. Chuẩn OpenSCENARIO | File .xosc xuất ra có hợp lệ theo XSD chính thức của ASAM không | lxml + XSD 1.0, 1.2, 1.3 | Có |
| 5. Tái hiện lỗi | Kịch bản dựng sẵn có đáp án biết trước, so kết quả esmini với đáp án | 3 script `repro_*.py` | Có |
| 6. Hệ thống trên dữ liệu thật | Chạy đủ pipeline trên cảnh nuScenes, đo 2 chỉ số chính thức | `scripts/run_benchmark_scenes.py` | **Chưa**: máy kiểm thử không có dữ liệu nuScenes |
| Frontend | Giao diện React | Vitest (51 ca) | Có: 51/51 đạt (Node 22, chạy trên bản sao tạm) |

**Môi trường đã dùng:** WSL2 Ubuntu, Python 3.14.4, pytest 9.1.1, FastAPI 0.143.3, `nuscenes-devkit` 1.2.0. Phần esmini chạy trên cả **3.8.2 và 3.9.0** (bản nhóm dùng), hai bản cho cùng kết quả. Code chạy trên một **bản sao**; folder gốc của nhóm không bị sửa.

**Khác với môi trường của nhóm:** Docker dùng Python 3.11, máy dev dùng 3.12, bản khóa ghi FastAPI 0.143.0. Kết quả ở đây vì vậy chưa chứng minh được code chạy đúng trên 3.11. Nên chạy lại trong image Docker trước khi nộp (ca TC-ENV-01).

## 3. Tiêu chí chất lượng và chấp nhận

Sản phẩm được chấm bằng 2 chỉ số, nên mỗi chỉ số cần hai loại bằng chứng. Một là con số đo trên dữ liệu thật. Hai là bằng chứng rằng cách đo không sai, kiểm bằng kịch bản có đáp án biết trước.

Dự án hiện chưa chốt ngưỡng nào; mọi ngưỡng trong code đều gắn nhãn `PROVISIONAL`. Các ngưỡng dưới đây là **đề xuất**, cần nhóm thống nhất trước khi dùng để kết luận đạt hay trượt.

| Chỉ số | Tiêu chí đề xuất | Vì sao |
| --- | --- | --- |
| Sai số phát lại, kịch bản có đáp án | RMSE ≤ 0,01 m cho mọi xe, kể cả xe xuất hiện muộn | Exporter sửa đúng thì đạt 0,000 m (mục 6 và 7). Sai số lớn hơn nghĩa là lỗi nằm ở pipeline chứ không phải ở dữ liệu |
| Sai số phát lại, dữ liệu nuScenes | Báo đủ trung vị, trung bình, p95, max của ADE và FDE; liệt kê mọi track có ADE > 1 m kèm nguyên nhân | Trung bình dễ bị vài track hỏng kéo lệch; nhóm từng báo mean 1,138 m nhưng max tới 95,7 m |
| Số kịch bản hợp lệ | 100% file .xosc hợp lệ theo XSD OpenSCENARIO chính thức | "Hợp lệ" phải đúng chuẩn, không chỉ là esmini chạy được. esmini bỏ qua lỗi cấu trúc, công cụ khác thì có thể không (L10) |
| Số kịch bản hợp lệ | 0 biến thể sai vật lý được tính là hợp lệ; cột tốc độ phải khớp với quãng đường đi được | Nếu bộ lọc cho lọt biến thể sai, con số "hợp lệ" bị thổi phồng (L6 ở đường sinh lô; L4 ở trình sửa chuyển động trên web) |
| Số kịch bản hợp lệ | Mỗi biến thể khác tham số có mã riêng; không đếm trùng | Hai biến thể khác nhau mà cùng mã sẽ ghi đè nhau. Đường sinh lô đã đạt; trình sửa chuyển động trên web thì chưa (L5) |

### Phễu lọc G1–G7 (theo code hiện tại)

| Cổng | Kiểm tra | Ngưỡng trong code |
| --- | --- | --- |
| G1 | File .xosc đúng tập con OpenSCENARIO hỗ trợ | `xosc-schema-v1` |
| G2 | esmini chạy xong, không lỗi | `simulator-completion-v1` |
| G3 | Quỹ đạo khớp làn đường | tỉ lệ khớp ≥ 0,95 |
| G4 | Khả thi vật lý | tăng tốc ≤ 5 m/s², phanh ≤ 8 m/s², giật ≤ 20 m/s³, tốc độ quay ≤ 1,5 rad/s |
| G5 | Không va chạm trước sự kiện chính | chỉ chạy khi có khai báo sự kiện, nếu không thì `skipped` |
| G6 | Đủ hiếm/nguy hiểm | TTC ≤ 2 s hoặc khoảng cách ≤ 1 m |
| G7 | Đủ khác biệt, không trùng lặp | khoảng cách đa dạng ≥ epsilon |

G3 cần bản đồ thật; tỉ lệ khớp đường đo được ở scene-0061 chỉ là 20/143 = 13,99%, xa ngưỡng 0,95. G4 chỉ đáng tin khi tốc độ và vị trí khớp nhau, điều mà L4 và L6 phá vỡ. G1 tên là `xosc-schema-v1` nhưng chỉ kiểm tập con mà code tự định nghĩa, không kiểm theo XSD chính thức, nên file sai chuẩn vẫn qua (L10).

### Tiêu chí vào / ra

- **Vào:** code cài được bằng `pip install -e .[dev,web]`; esmini ≥ 3.8 có trên máy; với mức 6, có `NUSCENES_ROOT` trỏ tới nuScenes.
- **Ra (được nộp):** 100% ca ưu tiên Cao ở mục 4 đạt; không còn lỗi mức Nghiêm trọng ở mục 7; số liệu 2 chỉ số đo lại được từ một lệnh duy nhất.
## 4. Ca kiểm thử

Có 20 ca, chia theo 3 nhóm: phát lại và chuẩn file (chỉ số 1), biến thể (chỉ số 2), web và môi trường. Mỗi ca có đáp án tính tay được, nên chỉ có Đạt hoặc Trượt. Cột Kết quả và Ưu tiên là danh sách chọn, nhóm tự cập nhật khi sửa lỗi. Ca ghi "(web)" kiểm trình sửa chuyển động trên web (`preview_variant`), không phải đường sinh lô biến thể.

| Mã | Kiểm tra | Dữ liệu vào | Mong đợi | Thực tế (bản 17/10) | Kết quả | Ưu tiên |
| --- | --- | --- | --- | --- | --- | --- |
| TC-R-01 | Phát lại xe có mặt từ t=0 | Ego 6 s, 10 m/s, quỹ đạo uốn nhẹ | RMSE ≤ 0,01 m | RMSE 0,099 m trên cả esmini 3.8.2 và 3.9.0, bằng 10 m/s × 0,01 s: xe trễ đúng một bước mô phỏng | Trượt | Cao |
| TC-R-02 | Phát lại xe vào cảnh muộn | Xe xuất hiện tại t=2 s, 8 m/s | RMSE ≤ 0,01 m, xe đứng yên trước t=2 s | RMSE 0,079 m (bản trước 2,53 m), bằng 8 m/s × 0,01 s | Trượt | Cao |
| TC-R-03 | Hộp bao xe đúng vị trí | 2 xe 4,5 m đối đầu, cách nhau 1,0 m, đứng yên | esmini không báo va chạm | esmini báo va chạm tại t=0 (cả 2 bản esmini) | Trượt | Cao |
| TC-R-04 | ADE/FDE trên cảnh nuScenes thật | Ít nhất 10 cảnh v1.0-mini | Báo đủ trung vị, p95, max; mọi track ADE > 1 m có giải thích | Không có dữ liệu trên máy kiểm thử | Chưa chạy | Cao |
| TC-R-05 | Test tự động exporter, độ đo, mô phỏng, tập con XOSC | 12 + 10 + 8 + 12 + 3 ca | Tất cả đạt | 45/45 đạt | Đạt | Trung bình |
| TC-R-06 | File .xosc đúng chuẩn OpenSCENARIO | 5 file .xosc do exporter sinh ra | Hợp lệ theo XSD chính thức 1.0, 1.2, 1.3 | 5/5 không hợp lệ: `VehicleCatalog` thiếu phần tử `Directory`; `StopTrigger` nằm trong `Story` thay vì `Storyboard` | Trượt | Cao |
| TC-V-01 | (web) Phanh làm xe chậm lại thật | Xe 10 m/s, phanh 3 m/s² từ t=1 s | Vị trí tăng chậm dần, tốc độ ≥ 0, xe dừng tại t≈ 4,3 s | Vị trí vẫn +10 m mỗi giây; tốc độ xuống −5 m/s; vẫn báo `valid` | Trượt | Cao |
| TC-V-02 | (web) Mã biến thể không trùng | Hai biến thể chỉ khác mức phanh (3 và 7 m/s²) | Hai mã khác nhau | Cùng một mã, nên ghi đè cùng thư mục `previews/` | Trượt | Trung bình |
| TC-V-03 | Nhân tốc độ theo hướng của chính xe đó | Xe cắt ngang chạy theo trục y, 5 m/s, nhân 1,5, qua `perturb_scenario` (sinh lô) | Toạ độ y cuối = 25 m (tính tay trong script) | y cuối vẫn 10 m; chỉ cột tốc độ ghi 7,5 m/s | Trượt | Cao |
| TC-V-07 | (web) Tăng tốc, đánh lái, tốc độ mục tiêu cũng đổi vị trí | Tăng tốc 3 m/s²; đánh lái 0,2; tốc độ mục tiêu 0; đều từ t=1 s | Vị trí cuối khác bản gốc; mỗi kiểu có mã riêng | Cả 3: x cuối vẫn 90 m, y vẫn 0; chỉ cột tốc độ hoặc hướng đổi; cả 3 cùng một mã | Trượt | Cao |
| TC-V-04 | Đổi tham số xe khác không làm đổi ego | Nhân tốc độ 1,5 cho cảnh | Ego giữ đúng dữ liệu ghi | Ego bị nhân theo: 90 m thay vì 60 m. Docstring của `perturb_scenario` ghi đây là cố ý | Cần quyết định | Trung bình |
| TC-V-05 | Một cấu hình hỏng không làm hỏng cả lô | Lô 12 cấu hình, 1 cái lệch thời gian âm | 11 biến thể được sinh, 1 bị ghi lỗi | `ValueError`, 0/12 được sinh | Trượt | Trung bình |
| TC-V-06 | Test tự động sinh biến thể, kiểm tra vật lý, xếp hạng, cổng | 13 + 11 + 8 + 11 + 8 ca | Tất cả đạt | 51/51 đạt | Đạt | Trung bình |
| TC-V-08 | Đếm số kịch bản hợp lệ trên dữ liệu thật | Lô biến thể trên ít nhất 10 cảnh nuScenes | Báo số sinh ra, số hợp lệ, số bị loại ở từng cổng G1–G7; đếm lại sau khi sửa L6 và L10 | Không có dữ liệu trên máy kiểm thử | Chưa chạy | Cao |
| TC-W-01 | Test tự động API web | 46 ca trong `test_web_api.py` | Tất cả đạt | 45 đạt, 1 bỏ qua vì cần nuScenes mini | Đạt | Trung bình |
| TC-W-02 | Lệnh chạy web trong README dùng được | `uvicorn PROJECT_N3_WEB.app:app --app-dir src` | Máy chủ lên, `/api/health` trả `ok` | `ModuleNotFoundError`; lệnh đúng `r2s_web.app:app` thì trả `ok` | Trượt | Trung bình |
| TC-W-03 | Test giao diện React | 51 ca Vitest, Node 22 | Tất cả đạt | 51/51 đạt trong 24,9 s | Đạt | Trung bình |
| TC-ENV-01 | Chạy toàn bộ test trong image Docker | Python 3.11, `pip install .[web,dev]` | Tất cả đạt | Chưa chạy | Chưa chạy | Cao |
| TC-ENV-02 | Thiếu gói tùy chọn thì test được bỏ qua, không hỏng | Không cài `nuscenes-devkit` | 1 ca báo bỏ qua | 1 ca hỏng (`test_missing_can_pose…`) | Trượt | Thấp |
| TC-ENV-03 | Báo cáo tổng hợp không lộ đường dẫn hay dữ liệu nuScenes | `test_benchmark.py`, `test_packaging.py` | Tất cả đạt | 6/6 đạt | Đạt | Trung bình |

TC-R-01 đến TC-V-07 dùng 3 script `repro_export.py`, `repro_bbox.py`, `repro_generation.py` trong `N3_bao_cao_loi_ban_moi`, cùng vài dòng Python gọi `preview_variant` và lxml. TC-R-06 kiểm bằng lxml với XSD chính thức của ASAM. Không script nào sửa code trong repo.

## 5. Kết quả thực thi

Bộ test tự động của nhóm đạt **347/348 ca Python** (1 ca bỏ qua vì cần nuScenes mini, chạy hết 9,3 giây) và **51/51 ca giao diện**. Trong 20 ca kiểm thử ở mục 4: **5 đạt, 11 trượt, 3 chưa chạy, 1 cần nhóm quyết định**.

Hai con số này không mâu thuẫn. Test của nhóm chủ yếu kiểm code chạy không lỗi và ra đúng định dạng. Chúng ít khi so kết quả với một đáp án tính tay. 11 ca trượt đều là loại so đáp án này, hoặc so với chuẩn OpenSCENARIO.

![pytest-cov, bản project-N3-main (2), chạy ngày 17/10/2026](bieu_do_do_phu_code.png)

*Nguồn: pytest-cov, bản project-N3-main (2), chạy ngày 17/10/2026*

Độ phủ tổng thể 83% (8.028 dòng lệnh). Các module ít được test nhất đều là nơi chạm dữ liệu thật hoặc chương trình ngoài. Đó cũng là nơi ca TC-R-04 và TC-ENV-01 chưa chạy được.

**Số liệu chỉ số trên dữ liệu thật (nhóm tự báo cáo, chưa kiểm lại độc lập):** theo `docs/reports/replay-fidelity-root-cause-and-fix.md`, nhóm chạy 850 cảnh v1.0-trainval bằng esmini 3.9.0. Có 808 cảnh hợp lệ và 42 cảnh bị loại vì không khả thi vật lý. ADE được tính trên 3.215 track.

| ADE (m) | Trung vị | Trung bình | p95 | Max |
| --- | --- | --- | --- | --- |
| Trước khi sửa | 0,300 | 16,040 | 95,067 | 279,088 |
| Sau khi sửa | 0,122 | 1,138 | 5,882 | 95,665 |

Sau khi sửa, track tệ nhất vẫn lệch 95,7 m. Con số này chưa được giải thích trong báo cáo, nên cần làm rõ trước khi nộp (TC-R-04). Ngoài ra, TC-R-01 cho thấy exporter hiện tại luôn làm xe trễ một bước mô phỏng, tức lệch thêm khoảng tốc độ × 0,01 s. Vì vậy một phần trung vị 0,122 m có thể đến từ lỗi này chứ không phải từ dữ liệu. Cần đo lại sau khi sửa L1 để biết chắc.

## 6. Kiểm thử theo phân phối

Lấy mẫu ngẫu nhiên 2.900 trường hợp cho thấy các lỗi ở mục 4 không phải trường hợp riêng. Chúng xảy ra trên gần như toàn bộ dải tham số. Một ca đơn lẻ ở mục 4 chỉ chứng minh lỗi có tồn tại. Mục này đo lỗi xảy ra thường xuyên đến đâu, và cho phép nói một câu định lượng khi một tính chất đạt.

**Cách làm.**

- Tham số được lấy mẫu phân phối đều trong dải ghi ở bảng dưới. Seed cố định là 20261017, nên chạy lại ra đúng các con số này.
- Mỗi mẫu được kiểm một tính chất có đáp án tính được, ví dụ "cột tốc độ phải khớp với quãng đường đi được". Cách này gọi là property-based testing.
- Khi 0/N mẫu lỗi, có thể nói với độ tin cậy 95% rằng tỉ lệ lỗi thật dưới 3/N (quy tắc số 3).
- Script `kiem_thu_phan_phoi.py` và `kiem_cach_sua.py`, chạy trên bản sao với esmini 3.9.0.

| Thí nghiệm | Dải tham số lấy mẫu | Số mẫu | Tính chất kiểm | Kết quả |
| --- | --- | --- | --- | --- |
| A. Phát lại | Tốc độ 0,5–30 m/s; độ cong ±0,1 rad/s; một nửa số xe xuất hiện muộn 0,5–5 s; bước 0,01 / 0,02 / 0,05 s | 300 cảnh, 600 track | RMSE ≤ 0,01 m | 8/600 đạt (1,3%), đều là xe chậm dưới 4,2 m/s. Trung vị 0,211 m, p95 1,183 m, max 1,455 m |
| A. Chuẩn file | 300 file .xosc của thí nghiệm A | 300 | Qua XSD 1.2 | 0/300 qua; cả 300 cùng mắc 2 lỗi của L10 |
| B. Trình sửa web | Phanh 0,5–8 m/s²; tăng tốc 0,5–5 m/s²; đánh lái 0,05–0,5; tốc độ mục tiêu 0–20 m/s; bắt đầu 0–4 s; nhóm đối chứng | 1.000 | Tốc độ khớp quãng đường (±0,5 m/s); hướng xe khớp hướng đi (±0,1 rad); mã không trùng | Xem bảng "Trình sửa chuyển động" |
| C. Sinh lô, nhân tốc độ | Góc của xe so với ego 0–180°; hệ số 0,5–0,9 hoặc 1,1–1,5 | 1.000 | Quãng đường mới = hệ số × quãng đường cũ (±1 m) | 82,6% vi phạm; xem biểu đồ cuối mục |
| D. Sinh lô, lưới tham số | 3 độ lệch thời gian ngẫu nhiên trong −1…1 s × 3 hệ số tốc độ | 500 lưới, 4.488 cấu hình | Cấu hình tốt vẫn được sinh | Cả 445 lưới có cấu hình xấu đều bị huỷ toàn bộ; mất 1.704 cấu hình tốt |

### Phát lại: sai số tỉ lệ với tốc độ × bước mô phỏng

![kiem_thu_phan_phoi.py, thí nghiệm A: 300 cảnh ngẫu nhiên, 600 track, esmini 3.9.0, seed 20261017](bieu_do_sai_so_phat_lai.png)

*Nguồn: kiem_thu_phan_phoi.py, thí nghiệm A: 300 cảnh ngẫu nhiên, 600 track, esmini 3.9.0, seed 20261017*

Với 441 xe có mặt từ t=0, tỉ số RMSE / (tốc độ × bước) luôn nằm trong 0,964–0,974. Xe xuất hiện muộn có tỉ số 0,02–0,97, trung vị 0,47, vì độ trễ tuỳ vào thời điểm xe xuất hiện rơi vào đâu trong bước. Hệ quả: với bước 0,05 s và xe chạy 30 m/s, riêng exporter đã gây sai số 1,5 m.

| Phiên bản .xosc (100 cảnh, 200 track) | Trung vị | p95 | Max | Tỉ lệ ≤ 0,01 m |
| --- | --- | --- | --- | --- |
| Hiện tại | 0,235 m | 1,292 m | 1,444 m | 1% |
| Đổi timing sang `absolute` | 0,000 m | 0,039 m | 0,086 m | 86,5% |
| `absolute` và trigger −1 | 0,000 m | 0,039 m | 0,086 m | 86,5% |

Chỉ cần đổi timing sang `absolute`: cả 153 track có mặt từ t=0 về đúng 0, tức tỉ lệ lỗi dưới 2% với độ tin cậy 95%. Xe xuất hiện muộn còn 27/47 track trên 0,01 m (max 0,086 m). Phần này cần xử lý thêm trường hợp thời điểm bắt đầu không trùng lưới bước. Đổi trigger thành −1 như `BAO_CAO_LOI.docx` đề xuất không cải thiện thêm, nên có thể bỏ.

### Trình sửa chuyển động trên web

| Thao tác | Số mẫu | Sai tính chất | Có tốc độ âm | Web vẫn báo hợp lệ |
| --- | --- | --- | --- | --- |
| Phanh | 197 | 197 (100%) | 144 | 197 |
| Tăng tốc | 215 | 215 (100%) | 0 | 215 |
| Đánh lái | 216 | 216 (100%, sai hướng) | 0 | 216 |
| Tốc độ mục tiêu | 189 | 175 (93%) | 0 | 175 |
| Đối chứng (hệ số tốc độ, khoảng cách) | 183 | 0 | 0 | 0 |

14 mẫu tốc độ mục tiêu "đạt" chỉ vì mục tiêu gần 10 m/s, bằng tốc độ cũ. Nhóm đối chứng 0/183 lỗi cho thấy phép kiểm không quá khắt khe. Nó cũng cho phép nói tỉ lệ lỗi của hai tham số đó dưới 1,6% với độ tin cậy 95%. Về mã biến thể: 1.000 thao tác chỉ tạo ra 184 mã, trong đó 817 thao tác phanh, tăng tốc, đánh lái và tốc độ mục tiêu dùng chung một mã.

### Sinh lô: lỗi nhân tốc độ theo góc

![kiem_thu_phan_phoi.py, thí nghiệm C: 1.000 mẫu, hệ số 0,5–0,9 và 1,1–1,5, xe 8 m/s trong 6 s](bieu_do_nhan_toc_do_theo_goc.png)

*Nguồn: kiem_thu_phan_phoi.py, thí nghiệm C: 1.000 mẫu, hệ số 0,5–0,9 và 1,1–1,5, xe 8 m/s trong 6 s*

`perturb_scenario` nhân quãng đường theo trục của ego, nên chỉ xe chạy cùng chiều hoặc ngược chiều ego (lệch dưới 15°) mới gần đúng. Xe cắt ngang (75–105°) lệch trung vị 14–16 m sau 6 s. Toàn bộ 82,6% số mẫu sai quá 1 m, trong khi cột tốc độ vẫn ghi đúng giá trị đã nhân. Đây là L6, nằm trên đường tạo ra chỉ số 2.

## 7. Lỗi phát hiện

Còn **10 lỗi**: 2 lỗi đã được nhóm sửa phần lớn so với bản trước, 6 lỗi vẫn nguyên, 2 lỗi mới tìm thấy. Nguy hiểm nhất là L10 và L6, vì chúng nằm trên đường tạo ra chỉ số "số kịch bản hợp lệ". L4 và L5 chỉ ảnh hưởng trình sửa chuyển động trên web, nhưng đó là phần giám khảo sẽ tự thao tác khi xem demo. Cách sửa L1–L7 có trong `BAO_CAO_LOI.docx`.

| Mã | Lỗi | Ảnh hưởng | Số đo | Mức độ | Trạng thái | Ca |
| --- | --- | --- | --- | --- | --- | --- |
| L10 | File .xosc sai cấu trúc chuẩn: `<VehicleCatalog directory=""/>` thay vì phần tử con `Directory`; `StopTrigger` đặt trong `Story` thay vì `Storyboard`. G1 không bắt được vì chỉ kiểm tập con tự định nghĩa | Mọi kịch bản được đếm là "hợp lệ" đều sai chuẩn ASAM. esmini vẫn chạy vì bỏ qua lỗi, công cụ kiểm XSD chặt thì có thể từ chối | 5/5 file không qua XSD 1.0, 1.2, 1.3. Sửa được bằng 2 thay đổi nhỏ trong `exporter.py`, kèm thêm bước kiểm XSD vào G1 | Nghiêm trọng | Mới phát hiện | TC-R-06 |
| L6 | `perturb_scenario` nhân quãng đường theo trục của ego, nhưng nhân cột tốc độ của mọi xe | Đường sinh lô tạo biến thể có tốc độ ghi khác quãng đường thật, ở xe cắt ngang hoặc ngược chiều | y cuối 10 m thay vì 25 m, cột tốc độ lại ghi 7,5 m/s | Cao | Còn | TC-V-03 |
| L4 | (web) `preview_variant` áp phanh, tăng tốc, đánh lái, tốc độ mục tiêu vào cột tốc độ hoặc hướng, không đổi vị trí | Quỹ đạo trên màn hình không đổi khi người dùng sửa chuyển động, mà web vẫn báo `valid` | Phanh: tốc độ xuống −5 m/s, vị trí không đổi; 3 kiểu còn lại cũng vậy | Cao | Còn | TC-V-01, TC-V-07 |
| L3 | `BoundingBox Center x` = 1/3 chiều dài xe, trong khi toạ độ là tâm xe | esmini báo va chạm giả, làm sai đánh giá nguy hiểm (G6) | 2 xe cách 1 m bị báo va chạm | Cao | Còn | TC-R-03 |
| L5 | (web) Mã xem trước chỉ tính 4 tham số (hệ số tốc độ, hướng, khoảng cách, thời gian). Mã của đường sinh lô thì đúng | Nhiều lần sửa khác nhau ghi đè cùng thư mục `previews/`, không truy lại được | Phanh 3 và 7 m/s² cùng mã | Trung bình | Còn | TC-V-02, TC-V-07 |
| L1 | Điều kiện bắt đầu `greaterThan` kèm timing `relative`, làm xe trễ một bước mô phỏng | Sai số phát lại có sẵn bằng tốc độ × bước thời gian, dù dữ liệu hoàn hảo | Ego RMSE 0,099 m (bản trước 0,496 m). Chỉ cần đổi timing sang absolute thì 153/153 track có mặt từ t=0 về 0,000 m (mục 6) | Trung bình | Đã sửa một phần | TC-R-01 |
| L2 | Xe vào cảnh muộn bị lệch thời gian | Tăng sai số phát lại ở xe xuất hiện giữa cảnh | RMSE 0,079 m (bản trước 2,53 m) | Trung bình | Đã sửa một phần | TC-R-02 |
| L7 | `_generate_batch` dừng cả lô khi gặp một `ValueError` | Một cấu hình xấu làm mất toàn bộ lô | 0/12 biến thể được sinh | Trung bình | Còn | TC-V-05 |
| L8 | README ghi `uvicorn PROJECT_N3_WEB.app:app` | Người mới không chạy được web theo hướng dẫn | `ModuleNotFoundError` | Thấp | Còn | TC-W-02 |
| L9 | `test_missing_can_pose_degrades_to_empty_capability_result` hỏng khi không cài `nuscenes-devkit` | Bộ test báo đỏ giả trên máy thiếu gói tùy chọn | 1 ca hỏng; thêm `pytest.importorskip("nuscenes")` là đủ | Thấp | Mới phát hiện | TC-ENV-02 |

Còn một câu hỏi thiết kế, chưa tính là lỗi: khi nhân tốc độ cho cảnh, ego cũng bị nhân (TC-V-04). Docstring của `perturb_scenario` ghi rõ điều này, nên đây là thiết kế có chủ ý. Tuy vậy, ego chạy khác dữ liệu ghi thì cảnh không còn là "cảnh thật", nên nhóm cần xác nhận và ghi vào `docs/current/decisions.md`.

## 8. Ma trận truy vết

Mỗi yêu cầu của đề tài đều có ít nhất một ca kiểm thử. Chỉ YC-07 được chứng minh đầy đủ; YC-05 và YC-06 mới được chứng minh một phần. Hai yêu cầu chính thức YC-01 và YC-03 vẫn còn ca trượt hoặc chưa chạy.

| Yêu cầu | Nội dung | Ca kiểm thử | Lỗi liên quan | Đã chứng minh? |
| --- | --- | --- | --- | --- |
| YC-01 (chỉ số 1) | Phát lại đúng quỹ đạo ghi | TC-R-01, TC-R-02, TC-R-04, TC-R-05 | L1, L2 | Chưa: còn sai số 0,08–0,10 m trên kịch bản có đáp án; chưa đo lại trên dữ liệu thật |
| YC-02 | Mô phỏng phát hiện va chạm đúng | TC-R-03 | L3 | Chưa |
| YC-03 (chỉ số 2) | Đếm đúng số kịch bản hợp lệ | TC-R-06, TC-V-03, TC-V-05, TC-V-06, TC-V-08 | L10, L6, L7 | Chưa: file sai chuẩn vẫn được đếm; chưa đếm trên dữ liệu thật |
| YC-04 | Biến thể đúng tham số đã chọn | TC-V-01, TC-V-03, TC-V-04, TC-V-07 | L4, L6 | Chưa |
| YC-05 | Sinh lô biến thể ổn định | TC-V-05, TC-V-06 | L7 | Một phần: chạy đúng khi mọi cấu hình hợp lệ |
| YC-06 | Web dùng được theo hướng dẫn | TC-W-01, TC-W-02, TC-W-03, TC-V-01, TC-V-02, TC-V-07 | L4, L5, L8 | Một phần: test API và giao diện đạt; trình sửa chuyển động tính sai; README sai lệnh chạy |
| YC-07 | Không lộ dữ liệu nuScenes (giấy phép phi thương mại) | TC-ENV-03 | — | Có, ở mức test tự động |
| YC-08 | Chạy lại được trên môi trường nộp bài | TC-ENV-01, TC-ENV-02 | L9 | Chưa |
| YC-09 | Kịch bản xuất ra đúng chuẩn OpenSCENARIO, dùng được ngoài esmini | TC-R-06 | L10 | Chưa |

## 9. Kết luận và khuyến nghị

**Chưa nên nộp bản này.** Tiêu chí ra ở mục 3 chưa đạt: còn 1 lỗi Nghiêm trọng (L10) và 10 ca ưu tiên Cao chưa đạt (7 trượt, 3 chưa chạy). Phần phát lại đã tiến bộ rõ: sai số xe vào muộn giảm từ 2,53 m xuống 0,079 m. Phần tạo ra chỉ số 2 thì chưa được sửa: file xuất ra sai chuẩn (L10), sinh lô còn L6 và L7. Phần lớn các lỗi này sửa được bằng vài dòng code.

### Việc cần làm, theo thứ tự

- [ ] Sửa L10 (2 chỗ trong `exporter.py`) và thêm bước kiểm XSD vào G1; chạy lại TC-R-06
- [ ] Sửa L6 và L7; chạy lại TC-V-03, TC-V-05
- [ ] Sửa L1 bằng cách đổi timing sang absolute (đã kiểm trên 200 track); xử lý tiếp xe xuất hiện muộn; sửa L3
- [ ] Sửa L4, L5 trên trình sửa chuyển động web; chạy lại TC-V-01, TC-V-02, TC-V-07
- [ ] Đưa 11 ca đang trượt vào `tests/` thành test hồi quy, để lỗi không quay lại
- [ ] Chạy TC-R-04 và TC-V-08 trên nuScenes; giải thích track lệch 95,7 m
- [ ] Chạy TC-ENV-01 (Docker, Python 3.11)
- [ ] Nhóm chốt ngưỡng ở mục 3 và xác nhận câu hỏi TC-V-04
### Cách chạy lại

```bash
pip install -e ".[dev,web,devkit]"
ESMINI_BIN_DIR=/duong/dan/esmini/bin python -m pytest -q --cov=real2scenario --cov=r2s_web
python3 -I repro_export.py "$PWD/src" "$ESMINI_BIN_DIR" "$PWD/_out"
python3 -I repro_bbox.py "$PWD/src" "$ESMINI_BIN_DIR" "$PWD/_out"
python3 -I repro_generation.py "$PWD/src"
# Kiểm XSD (tải OpenSCENARIOv1.2.xsd từ trang ASAM)
python3 -c "from lxml import etree; x=etree.XMLSchema(etree.parse('OpenSCENARIOv1.2.xsd')); print(x.validate(etree.parse('_out/as_is.xosc')), x.error_log)"
# Kiểm thử theo phân phối (mục 6), seed cố định
python3 -I kiem_thu_phan_phoi.py "$PWD/src" "$ESMINI_BIN_DIR" OpenSCENARIOv1.2.xsd "$PWD/_phan_phoi" 300
python3 -I kiem_cach_sua.py "$PWD/src" "$ESMINI_BIN_DIR" "$PWD/_cach_sua"
cd frontend && npm ci && npx vitest run
```

Tham số thư mục của script phải là **đường dẫn tuyệt đối**. Nếu dùng đường dẫn tương đối, esmini không ghi được file và script cho kết quả sai (xem bảng dưới).

### Tự rà soát bản kiểm thử này

Bản kiểm thử đã được tự rà soát ba lần để tìm chỗ sai, thiếu hoặc vô lý. Lần 2 đối chiếu từng con số với code và kết quả chạy lại. Lần 3 thay các ca đơn lẻ bằng lấy mẫu theo phân phối. Những chỗ tìm ra và cách đã xử lý:

| Lần rà | Vấn đề tìm ra | Loại | Đã xử lý |
| --- | --- | --- | --- |
| 1 | Lần chạy đầu có 1 test hỏng, dễ bị hiểu là lỗi sản phẩm | Sai | Cài đủ gói thì test đạt, nên đây là lỗi môi trường. Ghi lại thành L9, mức Thấp |
| 1 | Script tái hiện chạy với đường dẫn tương đối báo "không va chạm" ở cả hai trường hợp, tức là một kết quả Đạt giả | Sai | Chạy lại bằng đường dẫn tuyệt đối; L3 vẫn còn. Thêm cảnh báo ở phần Cách chạy lại |
| 1 | 347 test xanh dễ bị đọc thành "chất lượng tốt" | Vô lý | Thêm ca có đáp án tính tay; giải thích ở mục 5 vì sao xanh mà vẫn có lỗi |
| 1 | Đề tài không đưa ngưỡng mà tài liệu tự đặt ngưỡng đạt/trượt | Vô lý | Ghi rõ là đề xuất, cần nhóm chốt; nêu lý do từng ngưỡng |
| 1 | Số liệu ADE lấy từ báo cáo của nhóm | Thiếu | Ghi rõ là chưa kiểm lại độc lập; tạo TC-R-04 để đo lại |
| 1 | Chưa có ca cho môi trường nộp bài và cho giấy phép dữ liệu | Thiếu | Tạo TC-ENV-01, TC-ENV-03 và YC-07 |
| 1 | Chưa kiểm các lỗi cũ còn trong bản mới hay không | Thiếu | Chạy lại cả 7 lỗi: 2 đã sửa một phần, 5 còn nguyên |
| 2 | L4 và L5 bị ghi là làm sai chỉ số 2, nhưng chúng chỉ nằm ở trình sửa chuyển động trên web; đường sinh lô không có phanh | Sai | Sửa phạm vi L4, L5 và YC-03; hạ L4 từ Nghiêm trọng xuống Cao, L5 xuống Trung bình |
| 2 | Độ phủ đo lúc thiếu `nuscenes-devkit`, nên `nuscenes_backend` chỉ 72% (thực tế 84%) | Sai | Đo lại trong môi trường đủ gói, sửa biểu đồ |
| 2 | Đếm 52 ca Vitest bằng grep, thực tế 51 | Sai | Sửa theo kết quả chạy thật |
| 2 | Kiểm bằng esmini 3.8.2, trong khi nhóm dùng 3.9.0 | Thiếu | Chạy lại bằng 3.9.0; kết quả giống hệt |
| 2 | Chưa kiểm file .xosc theo XSD chuẩn, chỉ dựa vào G1 của nhóm | Thiếu | Thêm TC-R-06 và YC-09; phát hiện L10 |
| 2 | Chỉ số 2 chưa có ca đo trên dữ liệu thật | Thiếu | Thêm TC-V-08 |
| 2 | L4 mới kiểm riêng phanh | Thiếu | Thêm TC-V-07: tăng tốc, đánh lái, tốc độ mục tiêu cùng lỗi |
| 2 | Test giao diện chưa chạy | Thiếu | Chạy được 51/51 bằng Node của Windows trên bản sao tạm, đã xoá sau khi chạy |
| 2 | Ego bị nhân tốc độ được nêu như lỗi nghi vấn | Vô lý | Docstring cho thấy đây là thiết kế cố ý; giữ là câu hỏi thiết kế |
| 2 | Sai số 0,099 m chưa được giải thích | Thiếu | Đã xác định bằng tốc độ × bước thời gian (trễ một bước); ghi vào L1 và mục 5 |
| 3 | Mọi ca đều là vài kịch bản giả định: đủ chứng minh lỗi có tồn tại, nhưng không cho biết lỗi rộng đến đâu, và không đủ để kết luận "đạt" | Thiếu | Thêm mục 6: 2.900 mẫu ngẫu nhiên, báo tỉ lệ lỗi và cận trên 95% theo quy tắc số 3 |
| 3 | Giải thích "sai số = tốc độ × bước" mới dựa trên 2 xe | Thiếu | Kiểm trên 600 track, 3 bước mô phỏng; đúng với 441/441 xe có mặt từ t=0. Xe xuất hiện muộn có sai số nhỏ hơn |
| 3 | Cách sửa L1 trong `BAO_CAO_LOI.docx` (trigger −1 và timing absolute) chưa được kiểm trên nhiều cảnh | Thiếu | Kiểm trên 100 cảnh: chỉ cần timing absolute; trigger −1 không cải thiện; xe xuất hiện muộn còn sai tới 0,086 m |

**Giới hạn còn lại.** Chưa có ca nào chạy trên dữ liệu nuScenes thật (TC-R-04, TC-V-08). Khớp đường G3 mới có số đo cho một cảnh (scene-0061: 20/143 = 13,99%). TC-R-06 mới kiểm 5 file do script tạo ra; cần kiểm thêm trên file sinh từ cảnh thật. Kiểm thử hiệu năng và bảo mật triển khai nằm ngoài phạm vi tài liệu này.
