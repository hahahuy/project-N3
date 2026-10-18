# Project - N3: nuScenes → OpenSCENARIO MVP & Project Summary

> **Project name: `Project - N3`** (repo `project-N3`, codename `Real2Scenario`).
> This document is the long-term scope baseline for **Project - N3**.
>
> **Long-term scope baseline, not the current execution plan.** DEC-011
> supersedes the original CARLA-first MVP acceptance wording in this document:
> current MVP execution uses esmini and the internal Tier 1 kinematic preview;
> CARLA same-XOSC execution is post-MVP.
>
> **Trạng thái thực tế (cập nhật 2026-10-16):** tài liệu này là *baseline dài hạn*.
> Phần nào đã đo được thật sẽ được ghi rõ bằng số liệu và nhãn `PROVISIONAL`;
> phần nào vẫn là đề xuất chưa chốt vẫn giữ nguyên dạng đề xuất. Kế hoạch hiện hành là
> `docs/current/next-agent-handoff.md` và `docs/current/active-work.md`.
>
> **Ba điểm đã thay đổi so với baseline ban đầu:**
>
> 1. **Replay fidelity đã đo được trên 850 cảnh.** ADE mean `0.0411 m` (xem §5.2b).
>    Đây là phép đo *role A* trên lưới danh tính: chứng minh esmini chạy đúng quỹ đạo
>    được đưa vào. Nó **không** chứng minh bản đồ đúng vị trí thật.
> 2. **CP1 chưa đạt và chưa được giải thích.** Road-match thực tế là
>    **`20/143 = 13.99%`**, thấp hơn nhiều so với ngưỡng 95% đề xuất. Ba giải
>    thuyết đã bị loại trừ bằng đo; phần dư là **độ lệch ngang** chưa giải thích (xem §8).
> 3. **Browser WASM/esmini được duyệt làm trình chạy thay thế** (DEC-020), hiện
>    chạy ở chế độ diagnostic tại `/wasm-smoke` và chưa được đưa vào workspace.
>    Nó **không bao giờ** được dùng làm nguồn số liệu ADE/FDE.

*Tài liệu dành cho quản lý dự án. Mục tiêu: hiểu dự án làm gì, khó ở đâu, kiểm tra ở mốc nào, và ai sẽ dùng sản phẩm.*

## 1. Tóm tắt một đoạn

Dự án biến dữ liệu lái xe thật (nuScenes) thành kịch bản mô phỏng chuẩn **OpenSCENARIO**, chạy được trên **esmini** (CARLA là post-MVP theo DEC-011). Từ một cảnh thật, hệ thống sinh nhiều biến thể bằng cách đổi tốc độ và khoảng cách để tạo tình huống hiếm, nguy hiểm mà dữ liệu thật rất ít gặp. Để chứng minh mô phỏng đáng tin, ta **phát lại kịch bản và đo sai số quỹ đạo (ADE/FDE)**. Hai thước đo thành công: **sai số quỹ đạo khi phát lại** và **số kịch bản hợp lệ sinh ra được**.

**Hiện trạng (2026-10-16):** phép đo sai số quỹ đạo đã chạy trên **toàn bộ 850 cảnh** nuScenes `v1.0-trainval` với 3215 track và cho ADE mean `0.0411 m`. Phần còn lại của bài toán — chứng minh **bản đồ** đúng vị trí thật — vẫn chưa đạt (`13.99%`) và là nút thắt chính của dự án.

## 2. Vì sao đáng làm

- Dữ liệu thật hiếm tình huống nguy hiểm (cut-in gấp, phanh gấp). Các công ty như Applied Intuition và Foretellix đã bán sản phẩm thương mại cho đúng nhu cầu này.
- Chưa thấy pipeline open source nào làm trọn chuỗi: nuScenes → map OpenDRIVE → OpenSCENARIO → biến thể → đo sai số replay. Các mảnh rời đã có (ScenarioNet, Lanelet2-for-nuScenes, bài báo trích lane-change, CommonRoad converter).
- Giá trị chính là **tính minh bạch và khả năng kiểm chứng** của pipeline, không phải mô phỏng cảm biến đẹp.

## 3. Phạm vi MVP

**Trong phạm vi**

1. Dựng bản đồ OpenDRIVE (.xodr) từ map của nuScenes cho **một khu vực** (ví dụ Singapore One-North hoặc Boston Seaport).
2. Chuyển quỹ đạo ego và các vật thể đã gán nhãn của một số cảnh được chọn sang file .xosc.
3. Phát lại trên cả esmini và CARLA, ghi quỹ đạo, tính ADE/FDE so với dữ liệu gốc.
4. Sinh biến thể theo hai tham số: hệ số tốc độ và độ lệch khoảng cách/thời điểm.
5. Bộ lọc hợp lệ nhiều tầng và báo cáo "phễu" (bao nhiêu biến thể qua từng tầng).
6. Giao diện web gọn để chọn cảnh, xem so sánh quỹ đạo, chỉnh biến thể, tải file xosc/xodr.

**Ngoài phạm vi (làm sau)**

- Mô phỏng cảm biến (camera/lidar), neural reconstruction.
- Kiểm thử stack tự lái thật (closed-loop với planner).
- Phủ toàn bộ 4 khu vực bản đồ của nuScenes, mọi loại tình huống.
- Chạy trên simulator thứ ba (SUMO, MetaDrive).

## 4. Kiến trúc tổng quan

`nuScenes (annotation + map)` → **\[A\] Map builder** → `.xodr` ; **\[B\] Trajectory extractor** (nội suy, làm mượt, căn chỉnh) → **\[C\] OpenSCENARIO writer** → `.xosc` → **\[D\] esmini replay + ghi log** → **\[E\] Evaluator (ADE/FDE, heading, speed)** ; song song **\[F\] Variant generator** → **\[G\] Validity gates** → thư viện kịch bản + báo cáo → **\[H\] UI**.

## 5. Hai phần kỹ thuật cốt lõi

### 5.1 Dựng bản đồ xodr

nuScenes có map expansion với lane, lane connector, drivable area và đường tham chiếu dạng cung/đoạn thẳng. Đề xuất cách làm đơn giản cho MVP:

- Mỗi lane của nuScenes → **một road OpenDRIVE một làn**; mỗi lane connector → road nối trong một junction.
- Hình học lấy từ đường tâm của lane. Vì đường tâm nuScenes gồm đoạn thẳng và cung tròn, nó có thể ánh xạ khá tự nhiên sang `line`/`arc` của OpenDRIVE *(cần kiểm chứng trên dữ liệu thật)*.
- Chiều rộng làn: ước lượng từ polygon của lane, hoặc dùng giá trị cố định 3.5 m cho bản đầu.
- Bỏ qua ở MVP: biển báo, đèn giao thông, vạch kẻ chi tiết, làn đặc biệt.
- Hệ tọa độ: giữ nguyên hệ tọa độ map của nuScenes (mét) để quỹ đạo không phải biến đổi thêm, tránh một nguồn sai số.

**Điểm khó cần soi:** kết nối sai giữa road và junction làm xe "rơi" khỏi mạng đường; hình học liên tục không bị đứt gãy (vị trí và hướng) ở chỗ nối; map nuScenes thiếu hoặc lệch ở một số khu vực.

**Cách kiểm map:** (a) file qua trình kiểm tra/ nạp của esmini không lỗi; (b) vẽ chồng map xodr lên map gốc để kiểm tra độ lệch; (c) đo tỷ lệ điểm quỹ đạo thật nằm trong làn xodr (road-match rate).

### 5.2 Xử lý ADE/FDE chuẩn

Đây là chỉ số "chứng minh" nên phải thiết kế chặt, tránh tự kiểm tra vòng tròn.

- **Chuẩn so sánh (ground truth):** dùng **annotation gốc thô tại các mốc keyframe** (nuScenes gán nhãn khoảng 2 Hz). Không so với quỹ đạo đã làm mượt, vì khi đó sai số sẽ nhỏ một cách giả tạo.
- **Căn chỉnh thời gian:** lấy mẫu quỹ đạo replay của esmini đúng tại timestamp keyframe (nội suy tuyến tính trên log), cùng một hệ tọa độ.
- **ADE** = trung bình khoảng cách Euclid theo thời gian cho từng vật thể; **FDE** = khoảng cách tại thời điểm cuối. Báo cáo theo từng vật thể rồi tổng hợp: trung bình, trung vị, p95, max.
- **Chỉ số phụ:** sai số hướng (heading), sai số vận tốc, tách sai số dọc/ngang theo làn.
- **Hai chế độ replay, báo riêng:**
  - *Replay theo waypoint* (đi theo quỹ đạo): kỳ vọng sai số rất nhỏ; dùng để kiểm tra pipeline có bug không.
  - *Replay theo hành vi tham số hóa* (đổi tốc độ, đổi làn): sai số thật sự phản ánh độ trung thực của việc trừu tượng hóa.
- **Ngưỡng chấp nhận (đề xuất ban đầu, cần hiệu chỉnh):** ADE ≤ 0,5 m và FDE ≤ 1,0 m cho replay waypoint. Hiệu chỉnh bằng baseline: đo sai số chỉ do nội suy và nhiễu annotation trước khi chốt ngưỡng.

### 5.2b Kết quả đo thực tế (2026-10-16) — `PROVISIONAL`

Baseline hiện hành, đo trên **toàn bộ 850 cảnh** nuScenes `v1.0-trainval`, **3215 actor track**, esmini v3.9.0, tại `b52d423`/`79a4a8a`/`3372ff0`:

| Chỉ số | Giá trị | So với đề xuất ban đầu |
|---|---|---|
| ADE mean | **0.0411 m** | (đề xuất ≤ 0,5 m) |
| ADE median | **0.0348 m** | |
| ADE p95 | **0.1035 m** | |
| ADE max | **0.1726 m** | |
| FDE max | **0.2052 m** | (đề xuất ≤ 1,0 m) |

Ghi nhận quan trọng:

- **Số cảnh hợp lệ không đổi: 808/850.** Không có validity nào bị đánh đổi để lấy số đẹp.
- **Chi phí runtime +14 %** cho việc giảm timestep tích phân từ `0.05` xuống `0.01`.
- **Mọi số ADE/FDE ghi trước `b52d423` đều vô hiệu** và không được trích lại.

**Vai trò của chỉ số — đọc kỹ trước khi dùng.** Số này đo trên **lưới danh tính**
(kịch bản không bị chỉnh sửa), nên khung toạ độ chuẩn chỉ là phép tịnh tiến và xoay của
annotation gốc, phép biến đổi đó triệt tiêu trong khoảng cách Euclid. Vì vậy **position
ADE/FDE và sai số hướng là role A — phép đo thật so với dữ liệu lái xe gốc**: nó chứng minh
esmini tái tạo đúng quỹ đạo được đưa vào. `speed_mae_mps` là role B.

**Cái mà số này KHÔNG chứng minh:** độ đúng của **bản đồ**. Việc xe chạy đúng đường được vẽ
khác với việc đường được vẽ đúng vị trí thật. Phần thứ hai chưa đạt — xem CP1 ở §8.
Không được dùng `0.0411 m` để tuyên bố mô phỏng "chính xác 99.7%".

**Vì sao giảm được nhiều như vậy.** Không phải do tinh chỉnh tham số, mà do sửa một **lỗi mốc
thời gian**: actor xuất hiện giữa cảnh vẫn bị cho chạy ngay từ `t = 0`, chạy trước khoảng
`thời_gian_bắt_đầu × tốc_độ` mét — tức là mô phỏng **tự bịa chuyển động không có trong dữ
liệu ghi thật**. Cần **hai** điều kiện để sửa: giữ tốc độ bằng 0 cho tới khi quỹ đạo ghi bắt
đầu, và khớp `StartTrigger` của follow-trajectory với thời điểm bắt đầu thật. Giả thuyết
"map template là nguyên nhân chính" đã bị **phủ định bằng đo**.

**Chưa chốt ngưỡng.** Aggregate hiện chỉ có **micro mean** (gộp track), còn aggregate
**scene-macro** mà `docs/current/metric-benchmark-execution-plan.md` yêu cầu vẫn chưa có.
Ngưỡng chưa được đề xuất và sẽ không được đề xuất cho tới khi có scene-macro.
- **Quản lý ngoại lệ:** loại các vật thể xuất hiện quá ngắn (< 2 s), ghi rõ số lượng bị loại; báo cáo cả ca thất bại.

## 6. Sinh biến thể và định nghĩa "hợp lệ"

Biến thể: nhân tốc độ của một vật thể mục tiêu (ví dụ 0,7×–1,5×), dịch khoảng cách ban đầu hoặc thời điểm vào làn. Mỗi biến thể phải qua các tầng sau, theo thứ tự rẻ đến đắt:

| Tầng | Điều kiện | Công cụ |
| --- | --- | --- |
| G1 | File .xosc đúng schema OpenSCENARIO | XSD validate |
| G2 | esmini nạp và chạy hết kịch bản, không lỗi | esmini |
| G3 | Mọi vật thể luôn nằm trên đường (road-match) | log + xodr |
| G4 | Gia tốc, jerk, tốc độ trong giới hạn vật lý | tính từ log |
| G5 | Không va chạm ngoài ý muốn trước sự kiện chính | kiểm tra va chạm |
| G6 | **Đủ "hiếm"**: TTC tối thiểu hoặc khoảng cách tối thiểu dưới ngưỡng nhưng chưa va chạm | TTC / khoảng cách |
| G7 | Đa dạng: loại bản trùng gần nhau | khoảng cách trong không gian tham số |

**Số liệu báo cáo:** phễu từ N biến thể sinh ra → số qua từng tầng → số kịch bản hợp lệ cuối. Chỉ số "số kịch bản hợp lệ" của đề bài chính là đầu ra của G7.

## 7. Các điểm khó (rủi ro chính)

| # | Rủi ro | Mức | Giảm thiểu |
| --- | --- | --- | --- |
| R1 | Dựng xodr sai kết nối/hình học làm toàn bộ replay hỏng | Cao | Làm một khu vực nhỏ trước; kiểm map bằng road-match rate |
| R2 | Annotation 2 Hz thưa và nhiễu → quỹ đạo giật | Cao | Nội suy + làm mượt có tham số; đo baseline sai số riêng |
| R3 | ADE/FDE "đẹp" nhưng vô nghĩa vì so với dữ liệu đã làm mượt | Cao | Luôn so với annotation thô tại keyframe |
| R4 | Biến thể sinh ra phần lớn vô lý (va chạm, ra khỏi đường) | Trung bình | Bộ lọc nhiều tầng, báo cáo phễu |
| R5 | Giấy phép dữ liệu nuScenes (phi thương mại) | Thấp (mục đích học thuật) | Giữ trong phạm vi nghiên cứu; đọc điều khoản trước khi phát hành kịch bản hoặc map dẫn xuất |
| R6 | Phình phạm vi (sensor sim, UI đẹp, thời gian không giới hạn) | Trung bình | Khóa phạm vi MVP ở mục 3 |
| R7 | Khác biệt phiên bản và tập tính năng OpenSCENARIO giữa esmini và CARLA | Trung bình | Cố định phiên bản (Docker); chỉ dùng tập con OpenSCENARIO chạy được trên cả hai |

## 8. Các mốc kiểm tra (checkpoint)

Dự án do một người thực hiện, không giới hạn thời gian, nên các mốc là cổng chất lượng theo thứ tự, không phải hạn chót.

| Mốc | Nội dung | Tiêu chí đạt | Trạng thái 2026-10-16 |
| --- | --- | --- | --- |
| **CP0** | Chốt khu vực, 5–10 cảnh thử, môi trường tái lập được | Chạy được ví dụ mẫu của cả esmini và CARLA; repo và Docker chạy được | `PARTIAL` — nền tảng có; CARLA đã gặp handshake nhưng CP0 chưa có báo cáo mốc |
| **CP1** | Map xodr cho khu vực đã chọn | esmini và CARLA đều nạp không lỗi; road-match rate ≥ 95% trên cảnh thử *(ngưỡng đề xuất)* | `PARTIAL / PROVISIONAL` — **chưa đạt.** Baseline bất biến **`20/143 = 13.99%`**. Xem §8b |
| **CP2** | Một cảnh: nuScenes → xosc → replay | Cùng một file xosc chạy end-to-end trên cả hai simulator, có video/GIF so sánh | `CP2-A COMPLETE / CARLA UNVERIFIED` — interpreter và exact-pose đã test trên 48 file .xosc thật; same-XOSC CARLA là post-MVP |
| **CP3** | Evaluator ADE/FDE và baseline | Có baseline sai số nội suy; ADE/FDE cho từng simulator; ngưỡng được chốt từ baseline (hiện chưa có ngưỡng) | `PARTIAL` — baseline đo trên 850 cảnh (§5.2b); **ngưỡng chưa chốt** vì thiếu scene-macro |
| **CP4** | Sinh biến thể và bộ lọc hợp lệ | Báo cáo phễu; ≥ 1 loại tình huống hiếm có biến thể hợp lệ trên cả hai simulator | `PARTIAL` — G1-G7 đã đóng gói, 48/60 hợp lệ trên 5 cảnh; G3 đã evaluate 60 candidate và **0 đạt**; G6 luôn fail do nguyên nhân implementation |
| **CP5** | Đóng gói nghiên cứu | Benchmark và mã mở nguồn tái lập được; người ngoài chạy lại từ README | `PARTIAL` — có manifest + release evidence; sign-off của owner còn mở |
| **CP6** | Bản thảo bài báo | Kết quả định lượng đủ để trả lời câu hỏi nghiên cứu đã chốt | `OPEN` — câu hỏi nghiên cứu và evidence bundle chưa được duyệt |

### 8b CP1 — kết quả thật và vì sao chưa đạt (2026-10-16)

Baseline bất biến: **`20/143 = 13.99%`** road-match. Ngưỡng đề xuất là 95%. Đây là **hạn
chế lớn nhất của dự án**, và nó không phải hạn chế của ngưỡng mà là hạn chế của bản đồ.

**Ba giải thuyết đã bị loại trừ bằng đo** — đừng dùng lại chúng:

1. *"Thu hẹp corridor làm mất điểm"* — bị loại: với 143 trạng thái, đường gần nhất trên
   full map và trên corridor là **giống hệt nhau**.
2. *"Chuyển đổi bản đồ hoặc export OpenDRIVE sai"* — bị loại: phép so sánh native và
   canonical cho kết quả **trùng khớp tuyệt đối**, và XODR sinh ra tái tạo đúng corridor.
3. *"Cần quy ước actor reference hoặc đảo chiều làn"* — bị loại: các giả thuyết offset toàn
   cục không giải quyết được nhóm actor có độ lệch ngang.

**Phần dư còn lại:** **độ lệch ngang** giữa đường lái thật và đường trung tâm corridor được
sinh ra. Nó xuất hiện đều đặn trên cả 5 cảnh benchmark (centerline match
`0.0000`–`0.2500`), trong khi tính hợp lệ theo ngữ nghĩa làn vẫn cao (`66–100%`).

**Vì sao chưa sửa:** việc sửa đòi hỏi quyết định về quy ước hướng làn và tham chiếu actor —
đó là quyết định của **chủ sở hữu dự án**, không phải việc kỹ sư tự ý đổi. Baseline
`20/143` được giữ nguyên và sẽ không bị đổi.

### 8c Hướng kỹ thuật mới — browser WASM/esmini (DEC-020)

Một bản build Emscripten của esmini đã chạy được trong Web Worker của trình duyệt và
render được đường và actor trong Three.js. Nó được duyệt làm **trình chạy thay thế** cho
viewer hiện tại (vốn bị đánh giá là quá phức tạp để maintain).

Tuy nhiên nó hiện **chỉ ở chế độ diagnostic** tại `/wasm-smoke`, chưa đưa vào workspace, và
**tuyệt đối không** được dùng làm nguồn ADE/FDE: native esmini vẫn là nguồn số liệu duy
nhất. Các yêu cầu parity bắt buộc: tích phân ở `dt = 0.01` khớp native, Worker sở hữu
đồng hồ, và seek phải là reset rồi tích phân lại từ `t = 0`.

**Câu hỏi quản lý nên hỏi ở mỗi mốc:** Con số này đo cái gì? So với chuẩn nào? Có ca thất bại nào chưa được báo cáo? Có thể tái lập từ đầu không?

## 9. Đối tượng sử dụng (target audience) và hệ quả cho UI/UX

| Nhóm | Họ cần gì | Hệ quả thiết kế |
| --- | --- | --- |
| **Kỹ sư mô phỏng/kiểm thử ADAS-AV** (chính) | Tạo và kiểm chứng kịch bản nhanh, tải file chuẩn | Hiển thị rõ lý do một biến thể bị loại; xuất .xosc/.xodr; cấu hình có thể lưu và chạy lại |
| **Nhà nghiên cứu/sinh viên về AV testing** | Dữ liệu và chỉ số để so sánh, trích dẫn | Bảng ADE/FDE chi tiết, xuất CSV; ghi seed và phiên bản để tái lập |
| **Quản lý/người đánh giá dự án** | Thấy nhanh dự án có đạt mục tiêu không | Trang tổng quan: phễu hợp lệ, phân phối ADE/FDE, trạng thái từng checkpoint |
| **Kỹ sư ML cần dữ liệu tình huống hiếm** (thứ yếu) | Tập kịch bản đã lọc theo mức độ nguy hiểm | Lọc/sắp xếp theo TTC, loại tình huống |

**Nguyên tắc UX:** minh bạch hơn đẹp mắt (mọi con số phải truy được về nguồn); người dùng chuyên môn nên ưu tiên số liệu và so sánh trực quan; mỗi kết quả có nút "tái lập" (cấu hình + seed).

**Màn hình MVP:**

1. *Chọn cảnh:* danh sách cảnh nuScenes đã hỗ trợ, bản đồ thu nhỏ.
2. *So sánh quỹ đạo:* nhìn từ trên xuống, chồng quỹ đạo gốc và quỹ đạo replay; thanh thời gian; bảng ADE/FDE theo vật thể.
3. *Tạo biến thể:* thanh trượt tốc độ và khoảng cách, nút sinh hàng loạt.
4. *Kết quả biến thể:* phễu hợp lệ, danh sách biến thể kèm trạng thái (qua/rơi ở tầng nào), xem trước từng cái.
5. *Xuất:* tải .xosc/.xodr, báo cáo CSV/PDF.

Gợi ý công nghệ giao diện: Streamlit hoặc Gradio cho MVP (nhanh, đủ cho nhóm nhỏ); chỉ chuyển sang web app riêng khi có nhu cầu nhiều người dùng.

## 10. Công nghệ đề xuất

- **Dữ liệu:** nuScenes (bản mini để phát triển, bản đầy đủ khi đánh giá) và nuscenes-devkit với map expansion.
- **Mô phỏng:** esmini và CARLA (kèm ScenarioRunner), bắt buộc cả hai.
- **Ghi xosc/xodr:** Python, thư viện `scenariogeneration` hoặc tự viết XML; kiểm schema bằng XSD của OpenSCENARIO.
- **Đánh giá:** Python (numpy/pandas); đọc log esmini.
- **Đa dạng/độ hiếm:** TTC, khoảng cách tối thiểu; tham khảo ScenarioCharacterization.
- **Tái lập:** Docker, cấu hình YAML, seed cố định.

## 11. Thứ tự thực hiện (một người)

1. Map và dữ liệu: xodr builder, trích xuất quỹ đạo.
2. Mô phỏng và đánh giá: xosc writer, esmini, CARLA, ADE/FDE.
3. Biến thể: variant generator và bộ lọc hợp lệ.
4. Giao diện và tài liệu: làm sau cùng, tối giản.

Với một người thực hiện, ưu tiên pipeline và đánh giá trước, giao diện sau.

## 12. Quyết định đã chốt và câu hỏi còn mở

**Đã chốt**

1. **Mục đích:** nghiên cứu học thuật. Rủi ro giấy phép nuScenes (R5) giảm, miễn là giữ trong phạm vi nghiên cứu.
2. **Simulator:** bắt buộc chạy trên cả CARLA và esmini *(đã định nghĩa lại bởi DEC-011)*. **Hiện trạng:** MVP chạy trên **esmini**; CARLA same-XOSC là **post-MVP** và chưa được kiểm chứng. Lý do: CARLA chưa nạp được bản đồ OpenDRIVE tùy biến của dự án, còn esmini thì có.
3. **Nguồn lực:** một người, thời gian không giới hạn. Các mốc ở mục 8 là cổng chất lượng, không phải hạn chót.
4. **Sản phẩm:** công cụ mã mở và một bài báo.

**Còn mở**

1. Ngưỡng ADE/FDE: chưa rõ, sẽ chốt ở CP3 dựa trên baseline.
2. Loại tình huống hiếm ưu tiên: chưa rõ. Tạm đề xuất bắt đầu bằng cut-in và xe phía trước phanh gấp, vì chỉ cần đổi tốc độ và khoảng cách.
3. Điều khoản phát hành kịch bản và map dẫn xuất từ nuScenes: cần đọc trước khi công bố mã.

## 13. Kết quả bàn giao (deliverables)

- Repo mã nguồn mở có README, Docker, cấu hình mẫu.
- Bản đồ .xodr cho khu vực đã chọn và công cụ dựng map.
- Bộ kịch bản .xosc gốc và biến thể hợp lệ, chạy được trên cả esmini và CARLA.
- Báo cáo đánh giá: baseline sai số, ADE/FDE theo từng simulator, phễu hợp lệ, các ca thất bại.
- Bản thảo bài báo.
- UI demo và video demo ngắn (làm sau cùng).
