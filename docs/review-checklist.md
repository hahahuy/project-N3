# Checklist review code

Dùng checklist này cùng checkpoint milestone trong `mvp-roadmap.md`. Reviewer nên yêu cầu chỉnh sửa nếu một mục áp dụng được nhưng chưa tick mà không có lý do rõ ràng.

## Chung

- [ ] Ticket ID có trong tiêu đề hoặc mô tả pull request.
- [ ] Thay đổi đúng phạm vi ticket và tránh refactor không liên quan.
- [ ] Public function có type hint và docstring rõ ràng khi hành vi không hiển nhiên.
- [ ] Hành vi mới có automated test hoặc lý do được ghi rõ vì sao không thể tự động hoá.
- [ ] Error message xác định scenario/config/artifact lỗi mà không lộ secret.
- [ ] Không commit absolute path theo máy, credential hoặc output sinh ra dung lượng lớn.
- [ ] Yêu cầu giấy phép dataset vẫn hiển thị và được tuân thủ.

## Dữ liệu và schema

- [ ] Đơn vị là SI và được nêu trong field/docs.
- [ ] Coordinate frame và origin rõ ràng.
- [ ] Thứ tự thời gian được validate trước nội suy hoặc tính metric.
- [ ] Actor ID và scenario ID ổn định, duy nhất.
- [ ] Source token, source window, phiên bản dataset và phiên bản extraction được giữ lại.
- [ ] Dữ liệu thiếu/không hợp lệ tạo structured failure, không fallback im lặng.

## Hình học và metrics

- [ ] So sánh heading wrap góc đúng tại `-pi`/`pi`.
- [ ] Chính sách căn chỉnh thời gian rõ ràng và có test.
- [ ] Metric báo đơn vị, số sample và cách xử lý state thiếu.
- [ ] Threshold là config, có tài liệu và boundary test.
- [ ] Coordinate transform có test round-trip hoặc known-point.

## OpenSCENARIO và mô phỏng

- [ ] XML sinh ra được kiểm tra cấu trúc và có golden fixture ổn định khi phù hợp.
- [ ] Mọi path đến executable/map simulator được cấu hình bên ngoài.
- [ ] Timeout, return code, stdout và stderr của subprocess được ghi lại.
- [ ] Lỗi simulator vẫn phân biệt được với source/variant data không hợp lệ.
- [ ] Việc chọn map/template được giải thích trong artifact metadata.
- [ ] Local reconstruction không được trình bày như map conversion không mất thông tin.

## Sinh biến thể và validation

- [ ] Scenario sinh ra không mutate baseline.
- [ ] Parent scenario ID, seed, cấu hình tham số và phiên bản generator được lưu.
- [ ] Cùng input config/seed tái tạo được ID và thứ tự output.
- [ ] Feasibility check báo mọi lý do thất bại.
- [ ] Scenario invalid không thể xuất hiện trong output xếp hạng valid.
- [ ] Risk metric không được trình bày như bảo đảm an toàn.

## UI và demo

- [ ] Quỹ đạo recorded, replayed và generated dùng nhãn/style khác nhau.
- [ ] Control hiển thị đơn vị và miền giá trị cho phép.
- [ ] Kết quả hiển thị validity trước score.
- [ ] Tệp export có thể liên kết ngược tới source/provenance metadata.
- [ ] Demo flow hoạt động từ môi trường sạch bằng lệnh đã ghi trong docs.
