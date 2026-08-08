# PRODUCT REQUIREMENTS DOCUMENT (PRD)
Hệ thống Social Listening đa tác tử hỗ trợ phát hiện sớm phản hồi tiêu cực cho doanh nghiệp
Phiên bản: MVP 1.0

> Tài liệu gốc do nhóm dự án cung cấp. Bản sao này được lưu tại `docs/PRD.md`
> để làm cơ sở đối chiếu khi phát triển `src/` và `frontend/`.

## 1. Giới thiệu

### 1.1 Mục tiêu của tài liệu
Tài liệu này mô tả yêu cầu sản phẩm cho hệ thống Social Listening sử dụng kiến trúc Multi-Agent. Đây là tài liệu để cả nhóm thống nhất phạm vi phát triển, đồng thời làm cơ sở trao đổi với giảng viên trước khi bắt đầu xây dựng hệ thống.

PRD tập trung vào việc mô tả bài toán, đối tượng sử dụng, yêu cầu chức năng, luồng hoạt động và định hướng phát triển của sản phẩm. Các nội dung liên quan đến thiết kế kỹ thuật chi tiết sẽ được trình bày trong tài liệu thiết kế hệ thống (System Design Document).

## 2. Product Vision
Nhóm hướng tới xây dựng một nền tảng giúp doanh nghiệp theo dõi phản hồi của khách hàng trên nhiều nền tảng trực tuyến và phát hiện sớm những vấn đề có khả năng ảnh hưởng đến trải nghiệm người dùng hoặc uy tín thương hiệu.

Khác với các công cụ social listening chỉ dừng ở việc thu thập và thống kê dữ liệu, hệ thống sẽ sử dụng nhiều AI Agent phối hợp với nhau để phân tích, kiểm chứng và đánh giá độ tin cậy của từng cảnh báo trước khi gửi đến người sử dụng.

## 3. Bối cảnh
Hiện nay hầu hết doanh nghiệp đều nhận phản hồi từ rất nhiều nguồn khác nhau như Facebook, LinkedIn, Google Play, App Store, diễn đàn hay báo điện tử. Đội sản phẩm hoặc bộ phận chăm sóc khách hàng thường chỉ biết đến vấn đề khi số lượng cuộc gọi lên tổng đài tăng bất thường, mạng xã hội bắt đầu lan truyền nhiều bài viết tiêu cực, hoặc báo chí bắt đầu đưa tin.

## 4-9. Giải pháp, mục tiêu, phạm vi, đối tượng, user story, lý do chọn Multi-Agent
Xem chi tiết trong tài liệu gốc của nhóm. Tóm tắt các điểm khác biệt:
1. Sử dụng nhiều AI Agent thay vì một mô hình duy nhất.
2. Các agent kiểm chứng kết quả của nhau trước khi tạo cảnh báo.
3. Hệ thống tổng hợp phản hồi thành các **pain point** thay vì chỉ liệt kê bài viết.

## 10. Kiến trúc tổng quan

Hệ thống được định vị theo mô hình chuẩn ngành **SMCC (Social Media Command/
Control Center)**: một trung tâm điều hành mạng xã hội vận hành theo vòng lặp
4 trụ cột **Listen → Analyze → Respond → Report**, thay vì dừng lại ở việc
"phát hiện rồi báo" như một công cụ social listening thông thường.

```
LISTEN   → Collector Agent thu thập phản hồi THẬT (Google Play, App Store, ...)
ANALYZE  → Processing → Classification → Verification → Consensus → Pain Point Agent
           (làm sạch, phân loại cảm xúc/chủ đề, kiểm chứng chéo, gom thành pain point)
RESPOND  → Cập nhật trạng thái xử lý (Mới/Đang xử lý/Đã xử lý), người/đội phụ
           trách, ghi chú xử lý cho từng pain point — PATCH /api/v1/pain-points/{id}
REPORT   → Dashboard theo từng chủ đề + Báo cáo tổng quan cross-brand (KPI, SLA,
           so sánh giữa các chủ đề đang theo dõi) — GET /api/v1/report/summary
           → quay lại LISTEN (chu kỳ mới)
```
Chu kỳ Listen→Analyze: 15–30 phút (near real-time, xem Pipeline trong
`src/agents/graph.py`). Respond/Report là lớp nghiệp vụ con người thao tác
trên kết quả pipeline (không phải output của một Agent), nằm trong
`src/db/repository.py`, `src/api/routes.py` và `frontend/index.html`.

## 11-21. Kiến trúc nền tảng, yêu cầu chức năng/phi chức năng, thiết kế Agent, dữ liệu, kế hoạch, chỉ số, rủi ro, hướng phát triển
Xem toàn bộ nội dung chi tiết trong tài liệu PRD gốc được nhóm cung cấp (bản đầy đủ
lưu trong hệ thống quản lý tài liệu của nhóm). File này chỉ tóm tắt các mục cốt lõi
dùng làm tham chiếu khi lập trình `src/agents/`, `src/api/` và `frontend/`.

Các bảng dữ liệu chính (mục 15): `Users`, `Topics`, `Sources`, `Posts`,
`Predictions`, `PainPoints`, `Notifications` — tương ứng với
`src/models/schemas.py`.

Các AI Agent (mục 14): Collector, Processing, Classification, Verification,
Consensus, Pain Point — tương ứng với `src/agents/nodes/`.
