# Hướng dẫn làm Slides Thuyết trình — Real2Scenario

> Tài liệu nội bộ cho teammate chuẩn bị buổi trình bày sản phẩm.
> Người nhận: Ban giám khảo / khách hàng mục tiêu.
> Ngày lập: 2026-10-16 · Theo dõi tại commit `e9ad9b8`

---

## 0. ĐỌC TRƯỚC — Bốn điều bắt buộc

Bạn đang trình bày cho **ban giám khảo**. Nghĩa là họ sẽ hỏi. Bốn điều dưới đây quyết định
thành bại hay thất bại.

### 0.1 Đừng nói quá. Tuyệt đối không.

Dự án này ở trạng thái **implementation-complete nhưng acceptance-provisional** — nghĩa là
code chạy được, nhưng **chưa có kết luận khoa học nào được chấp nhận**.

Có những con số rất dễ bị hiểu sai thành "thành công". Nếu trình bày sai, bạn sẽ mất uy tín
khi giám khảo kiểm tra. Xem mục 4 để biết chính xác cách diễn giải từng con số.

### 0.2 Chỉ 3 con số "đẹp" được phép nói

| Con số | Cách được nói |
|---|---|
| `20/143 = 13.99%` | **Road-match rate của CP1 — và phải nói kèm là kết quả thấp, chưa đạt ngưỡng 95%.** Đây là hạn chế, không phải thành tích. |
| `48/60` biến thể hợp lệ | Phải nói rõ: "hợp lệ theo bộ lọc tự động", **không** phải "chính xác". |
| `0.03 m` ADE tốt nhất | Phải nói kèm: đây là **tự nhất quán**, không phải độ chính xác so với dữ liệu gốc. |

Mọi con số còn lại phải gắn nhãn `PROVISIONAL`.

### 0.3 Đây là bản build ĐANG ĐƯỢC SỬA

`npm run build` **đang fail** (TypeScript error tại `App.tsx:593`) do một đợt refactor
đang dở dang. Python test: `329 passed`. Frontend test: `48 passed` nhưng **build đỏ**.

→ **Không trình bày live từ bản build hiện tại** nếu chưa sửa xong. Hoặc dùng bản
đã commit `e9ad9b8` (build xanh, nhưng thiếu tính năng WASM).

### 0.4 Nếu bị hỏi "cái này dùng được chưa?"

Câu trả lời đúng, và đây là điểm mạnh chứ không phải điểm yếu:

> "Phần đọc và kiểm chứng đã dùng được thật trên dữ liệu nuScenes thật. Phần tạo biến thể
> và chạy lại tự động qua giao diện chưa mở — vì chúng tôi chưa quyết định xem có nên
> mở hay không. Chúng tôi giữ nguyên trạng thái 'chưa dùng được' thay vì làm ra vẻ chạy được."

Ban giám khảo đánh giá cao sự trung thực này hơn nhiều so với một demo bóng.

---

## 1. Bài toán (Slide 2–3) — 2 phút

### Slide 2: Vấn đề

**Nói:** Dữ liệu lái xe thật rất giàu về hành vi *thường lệ* và rất nghèo về hành vi
*nguy hiểm*. Cut-in gấp, phanh gấp, chen làn đột ngột — những tình huống quyết định an
toàn — gần như không xuất hiện trong dữ liệu thu thập bình thường. Nhưng đó lại đúng là
những tình huống ta cần kiểm thử nhiều nhất.

**Nói:** Hệ quả là mọi phương pháp kiểm thử hệ thống tự lái đều bị giới hạn bởi đúng
những tình huống mà ta có ít dữ liệu nhất.

### Slide 3: Khoảng trống

**Nói:** Có nhiều công cụ làm *một khúc* trong chuỗi, nhưng chúng tôi tìm thấy không có
pipeline nào mã nguồn mở làm trọn chuỗi, và làm được **có thể kiểm chứng**:

```
nuScenes (ghi thật) → bản đồ OpenDRIVE → kịch bản OpenSCENARIO
   → biến thể → chạy trên esmini → đo sai số → báo cáo
```

**Nói (điểm khác biệt, nói chậm):** Giá trị cốt lõi của chúng tôi **không phải là hình ảnh
đẹp**. Nó là **tính truy vết được**. Mọi con số trên màn hình đều truy được ngược về một
tệp, một mã băm, một phiên bản. Nếu không kiểm chứng được, chúng tôi hiển thị "chưa có"
chứ không hiển thị con số.

> **Mẹo trình bày:** câu cuối ở slide 3 là thứ phân biệt bạn với 90% sản phẩm khác. Đừng
> bỏ qua nó.

---

## 2. Giải pháp (Slide 4–6) — 4 phút

### Slide 4: Kiến trúc

```
ghi chép thật (nuScenes)
  ↓ adapter có cache
Kịch bản chuẩn + hồ sơ nguồn gốc (provenance)
  ↓
OpenDRIVE / OpenSCENARIO          [export layer]
  ↓
esmini (mô phỏng)                 [chạy thật]
  ↓
sai số + cổng chất lượng + bằng chứng  [đánh giá]
  ↓
Giao diện web                     [con người kiểm chứng]
```

**Nói:** Điểm cốt lõi thiết kế là **ranh giới canonical**. Dữ liệu nguồn đi qua một adapter
duy nhất; phần còn lại của hệ thống không bao giờ biết nuScenes tổ chức dữ liệu ra sao. Nhờ
vậy, khi thêm nguồn dữ liệu mới, chỉ thêm adapter — không phải viết lại toàn hệ.

### Slide 5: Sản phẩm chạy được

**Nói:** Pipeline này **đã chạy trên 5 cảnh thật của Singapore One-North**. Kết quả thật:

| Chỉ số | Kết quả | Cách nói |
|---|---|---|
| Biến thể sinh ra | 60 | |
| Hợp lệ qua bộ lọc | 48 | "qua bộ lọc tự động" |
| Lỗi simulator | 0 | điểm tốt, nói thẳng |
| Cảnh bị loại toàn bộ | 1 (`scene-0945`) | xem slide hạn chế |

**Nói (điểm đáng chú ý):** Một cảnh bị loại **toàn bộ 12 biến thể** vì dữ liệu gốc vi phạm
giới hạn gia tốc. Chúng tôi **không** nới giới hạn để cho qua. Đây là hệ thống bảo vệ chất
lượng hoạt động đúng.

### Slide 6: Giao diện — và những gì nó *không* làm

**Nói:** Giao diện tách rõ **ba loại bằng chứng**, không trộn lẫn:

1. **Bản đồ & quỹ đạo** (góc nhìn tác giả) — nơi bạn *kiểm chứng* bản đồ
2. **Bằng chứng cảm biến ghi thật** — dữ liệu nuScenes đã ghi, `LIDAR_TOP` 5 lần quét
3. **Mô phỏng trực tiếp** — esmini chạy thật, dữ liệu state thật

**Nói (quan trọng):** Ba loại này **không được gọi tên giống nhau**. Dữ liệu ghi thật không
bao giờ được gọi là "dữ liệu sau khi chỉnh sửa". Khi một thứ chưa có, giao diện hiển thị
**lý do cụ thể** — ví dụ "chưa mount esmini runtime" — chứ không hiển thị ô trống hay ảnh
giả.

> **Nếu giám khảo hỏi "cho tôi xem ảnh camera":** trả lời thật — môi trường build hiện
> tại không có chế độ render ảnh của esmini, nên hệ thống trả về `capture_viewer_unavailable`.
> Chúng tôi thiết kế để trả lời thẳng thay vì giả vờ. Đây là câu trả lời *được điểm*, không
> mất điểm.

---

## 3. Tính khả thi (Slide 7–8) — 3 phút

Đây là slide quyết định giám khảo có tin bạn không. **Đừng bỏ qua.**

### Slide 7: Bằng chứng đã chạy

```
Python test suite : 329 passed
Frontend tests    :  48 passed
Docs consistency  :  PASS
Build            : ⚠ đang sửa (xem mục 0.3)
```

**Nói:** Mỗi lần chạy CI tái lập được kết quả này.

**Sau đó phải nói thẳng (đừng để giám khảo tự phát hiện):**
> "Tuy nhiên, tôi muốn minh bạch một điều: con số 329 test này **không chứng minh** phần
> sửa dữ liệu cảm biến chạy đúng trên dữ liệu thật. Trong quá trình review, chúng tôi phát
> hiện một lỗi mà toàn bộ 322 test cũ vẫn pass — vì bộ test không có dữ liệu thật. Chúng tôi
> sửa rồi, và **đang chờ kiểm chứng lại trên dữ liệu thật**. Đây là việc đầu tiên cần làm."

Câu này **rất quan trọng**. Ban giám khảo chuyên nghiệp sẽ đánh giá cao việc bạn tự nhận ra
giới hạn của phương pháp kiểm chứng của chính mình.

### Slide 8: Đã phát hiện và xử lý sự cố thật

**Nói:** Trong quá trình review gần đây, nhóm đã tìm và sửa hai lỗi có tác động thật:

1. **Lỗi định danh bản ghi cảm biến.** Mọi API đều dùng sai mã bản ghi — 5 endpoint bị
   ảnh hưởng. Đã sửa.
2. **Lịch sử quét LiDAR bị cắt còn 1 dòng** thay vì 5, do đi sai chuỗi liên kết. Đã sửa.

**Nói:** Hai lỗi này cho thấy đúng điều giám khảo cần biết — phần lớn lỗi trong hệ thống này
**không nằm ở thuật toán**, mà nằm ở **việc nối đúng mã bản ghi nào với khung hình nào**.
Đó cũng là lý do hệ thống giữ hồ sơ nguồn gốc (provenance) cho từng đối tượng.

---

## 4. Hạn chế — LÀM MỘT SLIDE RIÊNG (Slide 9) — 2 phút

> **Không được bỏ slide này.** Đây là slide tách bạn khỏi những nhóm chỉ biết khoe hàng tốt.

### Các hạn chế (nói thẳng, không vòng vo)

| # | Hạn chế | Trạng thái thật |
|---|---|---|
| 1 | **Độ khớp làn đường chỉ 13.99%** (20/143 trạng thái) | Chưa đạt ngưỡng 95%. Đây là kết quả **thấp**. Đã phân tích: không phải do map, mà do **độ lệch ngang** giữa đường lái thật và đường trung tâm. **Chưa sửa** vì cần quyết định của chủ sở hữu dự án. |
| 2 | **G6/G7 (độ hiếm, độ đa dạng) chưa có ngưỡng khoa học** | Chỉ là chẩn đoán. Không được gọi là kết quả cuối. |
| 3 | **Hai nhóm chỉ số đang lẫn vai trò** | Chỉ số *tự nhất quán* (biến thể ↔ esmini) **khác** chỉ số *độ trung thực* (phát lại ↔ dữ liệu ghi thật). Chúng tôi **đang tách**, chưa tách xong. |
| 4 | **Ảnh esmini chưa chạy được** | Môi trường build không có chế độ render. Hệ thống trả `capture_viewer_unavailable`. |
| 5 | **Chưa sinh được cảm biến sau chỉnh sửa** | Cảm biến "sau edit" vẫn là `unsupported`. Chỉ có cảm biến gốc. **Đây là giới hạn bản chất, chưa phải lỗi.** |
| 6 | **Chạy multi-simulator chưa xong** | CARLA là post-MVP. Hiện chỉ esmini. |
| 7 | **Giao diện đang ở giữa refactor** | Một số chức năng backend đã có nhưng chưa mở nút trên UI. |

### Cách nói về hạn chế #3 (giám khảo chuyên nghiệp sẽ hỏi đúng chỗ này)

> "Đây là điểm chúng tôi muốn nói thẳng nhất. Hiện có hai họ chỉ số khác nhau về bản chất:
> một họ đo *sự nhất quán* giữa kịch bản mình xuất và thứ esmini chạy ra — cái này nhỏ và
> tốt. Họ còn lại đo *độ trung thực* giữa phát lại và dữ liệu lái xe thật — cái này mới là
> cái thực sự chứng minh mô phỏng đáng tin, và nó là cái chúng tôi **chưa** đạt được, vì
> đường làn chưa khớp (13.99%). Chúng tôi không muốn trộn hai cái này thành một con số đẹp."

---

## 5. Định hướng phát triển (Slide 10–11) — 2 phút

### Slide 10: Ba bước gần nhất

```
1. Đóng nốt đường làn      → mở khóa chỉ số độ trung thực
                             (đây là nút thắt duy nhất còn lại)
2. Kiểm chứng trên dữ liệu thật → xác nhận các sửa lỗi cảm biến
3. Mở hoặc chốt phạm vi UI  → quyết định của chủ sở hữu, cần chốt
```

**Nói:** Ưu tiên số 1 vì nó là **nút thắt duy nhất**. Khi đường làn khớp, toàn bộ chuỗi chỉ
số có ý nghĩa trở lại. Chúng tôi không đầu tư thêm tính năng cho tới khi đóng được nút thắt
này — và đó là một quyết định có chủ đích.

### Slide 11: Tầm nhìn dài hạn

**Nói:** Kiến trúc hiện tại cố tình tách rõ lớp. Khi đường ống ổn định, kiến trúc này có thể
mở rộng sang nhiều nguồn dữ liệu lái xe khác mà **không phải viết lại phần lõi** — chỉ thêm
adapter.

**Nói:** Hướng nghiên cứu không phải "làm simulator đẹp hơn", mà là **đo được độ tin cậy của
việc biến dữ liệu lái xe thật thành tình huống kiểm thử tái lập được**.

---

## 6. Slide kết (Slide 12) — 1 phút

**Nói:** Tóm lại ba điều:

1. **Đã có:** pipeline trọn vẹn, chạy trên dữ liệu thật, mọi con số truy được ngược về nguồn.
2. **Chưa có:** đường làn chưa khớp (13.99%) — và đây là nút thắt thật, chúng tôi nói thẳng.
3. **Bước tiếp theo:** đóng nút thắt đường làn, rồi tái kiểm chứng toàn bộ chuỗi.

**Kết bằng:** "Chúng tôi thà đến trình bày một hệ thống còn thiếu, có nút thắt đã biết và
đường đi đã vạch, hơn là một hệ thống trông hoàn chỉnh nhưng không kiểm chứng được."

---

## 7. Câu hỏi giám khảo thường gặp — chuẩn bị trước

### "Sao con số đường làn chỉ có 14%?"

> "Đúng, và đây là hạn chế lớn nhất. Chúng tôi đã phân tích và loại trừ được nguyên nhân:
> không phải do cách dựng bản đồ, cũng không phải do sai thuật toán — bản đồ dựng ra khớp
> với dữ liệu gốc. Phần còn lại là **độ lệch ngang** giữa đường lái thật và đường trung tâm
> làn. Chúng tôi chưa sửa vì việc sửa đòi hỏi quyết định về quy ước hướng làn, và quyết
> định đó thuộc về chủ sở hữu dự án chứ không phải kỹ sư."

### "ADE/FDE của các bạn là gì?"

> "Cần phân biệt rõ: ADE chúng tôi đang báo là **tự nhất quán** giữa kịch bản xuất và
> esmini — khoảng 0.03 m ở cảnh tốt nhất. Nó **không** phải độ chính xác so với dữ liệu lái
> xe thật. Cái thứ hai chính là cái bị chặn bởi vấn đề đường làn, và chúng tôi chưa có con
> số đáng trình bày cho nó."

### "Ổn định thế nào? Chạy được bao lâu?"

> "Bộ test tự động ổn định. Nhưng tôi phải nói thêm một điểm vận hành: trong quá trình
> chuẩn bị demo, chúng tôi đã gặp một sự cố mà container *nhìn* vẫn bình thường nhưng thực
> tế đã chết, do cách supervisor khởi động lại tiến trình. Chúng tôi đã ghi nhận và đang
> sửa, nhưng chưa sửa xong. Đây là loại lỗi mà demo trực tiếp rất dễ gặp."

### "Có mở rộng được sang dữ liệu khác không?"

> "Kiến trúc có, chúng tôi thiết kế cho việc đó. Thực tế thì chưa làm, và tôi không muốn
> hứa trước khi có bằng chứng."

### "Có nguy cơ phụ thuộc nuScenes không?"

> "Không ở phần lõi. Toàn bộ phần lõi chỉ biết 'kịch bản chuẩn + hồ sơ nguồn gốc'. Mọi thứ
> đặc thù nuScenes nằm sau một adapter duy nhất. Đây là điều chúng tôi đã kiểm tra bằng
> kiến trúc phân lớp, không phải chỉ bằng ý kiến."

### "So với ScenarioNet / Lanelet2 thì sao?"

> "Những công cụ đó làm tốt những khúc của chuỗi. Điểm khác biệt của chúng tôi là khép
> kín chuỗi với bước kiểm chứng — và bước kiểm chứng đó mới là bước dễ bị làm ẩu, dễ bị
> tự kiểm tra vòng tròn nhất."

---

## 8. Checklist trước khi trình bày

- [ ] Dùng đúng build (xem mục 0.3) — **không demo trên build đỏ**
- [ ] Có sẵn ảnh chụp màn hình dự phòng, trong trường hợp mạng/máy hỏng
- [ ] Thuộc con số ở slide 5 và 9
- [ ] Thuộc cách trả lời ở mục 7, đặc biệt câu về 13.99% và ADE
- [ ] Mỗi lần nói "đã chạy" → kiểm tra có đúng là đã chạy trên dữ liệu thật không
- [ ] Không nói "chính xác", "hoàn hảo", "đã sẵn sàng production" ở bất kỳ slide nào
- [ ] Chuẩn bị trả lời câu "nếu mai mở rộng ra 4 khu vực thì sao?" → trung thực:
      chưa làm, cần mở rộng bản đồ trước
- [ ] Cảm ơn và mời hỏi — **đừng kết thúc bằng việc tự khen**

---

## Phụ lục: Nguồn số liệu

| Con số | Nguồn trong repo |
|---|---|
| `20/143 = 13.99%` | `docs/reports/cp1-corridor-external-evidence.md` |
| 60 biến thể / 48 hợp lệ / 0 lỗi sim | `docs/reports/cp3-benchmark-run-evidence.md` |
| ADE mean 15.31 · median 0.29 | cùng trên |
| `scene-0945` bị loại toàn bộ | cùng trên |
| 13 helper API chưa có UI | `docs/current/viewpanel-makeover-prompt.md` |
| Build đang fail | `frontend/` `npm run build`, `App.tsx:593` |

**Nguyên tắc:** nếu không tìm được con số trong repo, **đừng đưa lên slide**. Hãy nói "phần
này chúng tôi chưa đo" — đó là câu trả lời mà giám khảo chấp nhận được.