# Đặc tả sản phẩm: Real2Scenario

## 1. Bài toán

Dataset lái xe tự hành được ghi nhận chứa các tương tác thực tế, nhưng khó phát lại, chỉnh sửa và khai thác có hệ thống cho kiểm thử an toàn. Team cần một đường đi có thể tái lập: từ một đoạn quỹ đạo đã ghi nhận đến scenario sẵn sàng mô phỏng, rồi đến các biến thể có kiểm soát của scenario đó.

## 2. Tuyên bố sản phẩm

Real2Scenario là workbench khai thác scenario, chuyển một tương tác nuScenes được chọn thành bản phát lại OpenSCENARIO, định lượng độ trung thực khi phát lại, rồi tạo biến thể tình huống hiếm hợp lệ bằng cách thay đổi một tập nhỏ tham số vật lý.

Sản phẩm là công cụ kiểm thử và nghiên cứu. Nó không đưa ra tuyên bố an toàn cho phương tiện và không thay thế đánh giá closed-loop của autonomy stack.

## 3. Người dùng chính và công việc cần làm

| Người dùng | Công việc cần hoàn thành |
| --- | --- |
| Nhà nghiên cứu AV | Biến tương tác đã ghi nhận thành test case mô phỏng có thể tái lập. |
| Kỹ sư safety/test | Mở rộng coverage quanh edge case quan sát được mà không phải tự viết từng scenario. |
| Người review/người xem demo | Hiểu provenance, chất lượng replay và lý do một case sinh ra được coi là hợp lệ, đáng chú ý. |

## 4. Kết quả MVP

Với ít nhất ba đoạn ghi nhận được chọn, người dùng có thể:

1. Xem quỹ đạo ego và actor liên quan trong top-down viewer.
2. Xuất baseline OpenSCENARIO và chạy bằng esmini.
3. So sánh quỹ đạo ghi nhận với quỹ đạo replay cùng các metric fidelity.
4. Sinh ít nhất 20 biến thể xác định bằng cách đổi tốc độ, khoảng cách hoặc thời điểm.
5. Review kết quả validation, tải tệp `.xosc` và báo cáo metadata đi kèm.

M4 delivers this as a local web demo: a React frontend served from the
developer machine calls a local FastAPI backend over HTTP. The backend runs
the existing Python pipeline with local CPU resources, optional locally
installed esmini, and a project-relative output directory. M4 does not require
accounts, shared-server deployment, object storage, or multi-user access.

## 5. Trải nghiệm demo

UI MVP có bốn khu vực:

| Khu vực | Hiển thị | Tương tác bắt buộc |
| --- | --- | --- |
| Trình duyệt scenario | Các source segment và nhãn sự kiện | Chọn một segment. |
| Phát lại top-down | Ego, actor liên quan, timeline, đường original/replay | Phát, kéo thời gian, chọn actor. |
| Điều khiển biến thể | Hệ số tốc độ, initial gap, timing offset, số lượng sinh | Sinh biến thể xác định. |
| Kết quả | Validity, RMSE, sai số tốc độ, TTC/khoảng cách nhỏ nhất, export | Lọc và xem một kết quả. |

### Luồng demo hoàn chỉnh

Người dùng mở ứng dụng local trong trình duyệt và đi qua một luồng duy nhất:

1. Chọn hoặc nạp một scenario artifact từ danh sách local.
2. Kiểm tra scenario ID, coordinate frame, duration, actor và provenance.
3. Xem trajectory recorded trong top-down viewer; recorded, replayed và
   generated path phải có style khác nhau.
4. Chạy hoặc xem baseline replay nếu artifact có replay output, sau đó xem
   overlay và fidelity metrics.
5. Chọn speed multiplier, initial gap delta, timing offset, batch size và seed.
6. Bấm generate; FastAPI gọi batch generator hiện có và trả về job/result
   status mà không để React tự tính trajectory.
7. Xem validation trước ranking; invalid variant phải có structured reasons.
8. Xem ranking components chỉ cho variant hợp lệ; simulator-failed phải hiển
   thị riêng với exit code, stderr và tool context nếu có.
9. Chọn một result để xem trajectory, metadata, metrics và artifact links.
10. Tải canonical JSON, `.xosc`, replay trace hoặc report từ ứng dụng.

Sau khi backend/frontend đã khởi động, reviewer không cần sửa file trực tiếp
hoặc chạy thêm terminal command trong luồng demo.

Demo chuẩn là tương tác xe phía trước phanh. Cut-in là loại sự kiện thứ hai được ưu tiên. Người đi bộ qua đường và giao lộ thuộc post-MVP vì map alignment và validation khó hơn.

## 6. Yêu cầu chức năng

| ID | Yêu cầu | Điều kiện chấp nhận MVP |
| --- | --- | --- |
| FR-01 | Nạp source segment vào canonical scenario model. | Segment có ego, 1-3 actor được chọn, state theo thời gian, kích thước và provenance. |
| FR-02 | Phát hiện/chọn actor liên quan. | Lý do chọn được lưu: khoảng cách, TTC, quan hệ lane hoặc lựa chọn tay đã cấu hình. |
| FR-03 | Xuất baseline `.xosc`. | XML sinh ra parse được và esmini khởi động thành công. |
| FR-04 | Phát lại và so sánh quỹ đạo. | Báo cáo có position RMSE, final displacement, heading MAE và speed MAE. |
| FR-05 | Sinh biến thể có ràng buộc. | Mỗi biến thể lưu parent ID, cấu hình tham số, phiên bản generator và random seed. |
| FR-06 | Validate scenario sinh ra. | Báo cáo tách validation động học, map/road và simulator. |
| FR-07 | Xếp hạng scenario hữu ích. | Kết quả có điểm risk/novelty minh bạch và các thành phần thô. |
| FR-08 | Xuất artifact để review. | Có `.xosc`, canonical scenario JSON, replay trace và JSON report cho từng kết quả. |

## 7. Các mục tiêu không thuộc MVP

- Converter không mất thông tin từ nuScenes map sang OpenDRIVE.
- Tích hợp CARLA đầy đủ, render camera hoặc sinh sensor.
- Đánh giá planning/control closed-loop.
- Mô hình AI sinh scenario.
- Hỗ trợ mọi tính năng OpenSCENARIO hoặc mọi sự kiện giao thông.
- Tuyên bố scenario sinh ra thể hiện xác suất ngoài đời thực.

## 8. Metrics

| Metric | Định nghĩa | Mục đích |
| --- | --- | --- |
| Position RMSE | Căn bậc hai sai số bình phương trung bình của khoảng cách phẳng giữa state ghi nhận/replay đã căn chỉnh. | Fidelity replay chính. |
| Final displacement error | Khoảng cách phẳng tại timestamp cuối đã căn chỉnh. | Phát hiện drift tích luỹ. |
| Heading MAE | Trung bình sai số tuyệt đối yaw đã wrap. | Phát hiện sai khác hướng. |
| Speed MAE | Trung bình sai số tuyệt đối vận tốc. | Phát hiện sai khác động học. |
| Tỷ lệ biến thể hợp lệ | Số biến thể hợp lệ chia cho số biến thể sinh ra. | Đo output có thể dùng. |
| Tỷ lệ simulator hoàn thành | Số lượt chạy không lỗi simulator chia cho số lượt thử. | Độ tin cậy tích hợp. |
| TTC/khoảng cách nhỏ nhất | Giá trị nhỏ nhất theo từng cặp trong replay. | Tín hiệu rủi ro, không phải bằng chứng an toàn. |
| Diversity | Cấu hình tham số hợp lệ hoặc cụm quỹ đạo duy nhất. | Phát hiện output trùng lặp. |

Threshold là cấu hình, không phải chân lý phổ quát. Team phải ghi nhận phiên bản threshold trong mọi lần đánh giá.

## 9. Ràng buộc dữ liệu và giấy phép

Các tệp panoptic mini đã commit không đủ để trích xuất trajectory. Pipeline còn cần metadata nuScenes như `scene.json`, `sample.json`, `sample_data.json`, `sample_annotation.json`, `ego_pose.json` và metadata calibration. Cần map metadata để trích xuất có nhận biết lane.

Nội dung nuScenes trong repository tuân theo `data/LICENSE`. Team phải giữ yêu cầu ghi công và phi thương mại/share-alike, không commit credential, và không công bố dữ liệu hoặc artifact dẫn xuất trái điều khoản đó.

## 10. Definition of Done

MVP chỉ hoàn thành khi các bằng chứng sau đã được commit hoặc đính kèm release:

- Ba source scenario ID có provenance và cấu hình source window.
- Một baseline replay report thành công cho mỗi source scenario.
- Một batch ít nhất 20 biến thể cho mỗi source scenario.
- Validation summary thể hiện số valid, invalid và simulator-failed.
- Demo kịch bản 3 phút chạy được mà không sửa XML bằng tay.
- Automated tests pass cho schema, chuyển đổi toạ độ, tính metric và cấu hình biến thể xác định.
- Local web demo khởi động theo một command đã ghi, chạy được flow chọn ->
  replay -> generate -> validate -> rank -> export trên fixture đã tài liệu.
- UI smoke test chứng minh recorded/replayed/generated path và ba trạng thái
  valid/invalid/simulator-failed được phân biệt.
