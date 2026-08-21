# Nghiên cứu sơ bộ: thu thập dữ liệu LinkedIn / Facebook

> Phạm vi: tài liệu phân tích, **không phải hướng dẫn triển khai**. Mục tiêu là hiểu rõ vì sao
> hai nguồn này khó/không nên tự scrape ngay ở MVP, và các hướng đi khả thi cho giai đoạn mở
> rộng sau MVP. `LinkedInCollector` hiện tại chỉ là stub (`src/pipeline/collectors/linkedin.py`)
> trả về danh sách rỗng.

## 1. Vì sao không scrape trực tiếp ngay bây giờ

**LinkedIn**
- Không có API công khai cho phép bên thứ ba tìm bài viết/bình luận theo từ khóa (LinkedIn Marketing API chỉ phục vụ chủ sở hữu trang/quảng cáo, không phải social listening tự do).
- Phần lớn nội dung (bài viết, bình luận) chỉ xem được sau khi đăng nhập → muốn scrape buộc phải dùng cookie/session của một tài khoản thật.
- Điều khoản sử dụng của LinkedIn cấm rõ ràng việc scrape tự động; hệ thống chống bot của họ phát hiện khá nhanh (rate limit bất thường, pattern truy cập không giống người dùng thật) và khóa tài khoản đứng tên thật của thành viên trong nhóm — rủi ro cao hơn nhiều so với lợi ích ở giai đoạn MVP.

**Facebook**
- Tương tự: Graph API chỉ cho phép đọc dữ liệu Trang (Page) do chính mình quản lý hoặc dữ liệu public rất giới hạn qua các sản phẩm được duyệt (App Review) — không có endpoint tìm bài viết công khai theo từ khóa cho bên thứ ba.
- Scrape HTML/private API nội bộ của Facebook vi phạm ToS tương tự LinkedIn, và Facebook cũng có hệ thống phát hiện bot mạnh (checkpoint xác minh danh tính, khóa tạm thời, khóa vĩnh viễn).

## 2. "Luân phiên tài khoản" là gì và vì sao chỉ dừng ở mức nghiên cứu

Về mặt kỹ thuật, "account rotation" (luân phiên nhiều tài khoản + proxy IP khác nhau cho mỗi
tài khoản, giới hạn tần suất truy cập trên từng tài khoản) là kỹ thuật phổ biến trong ngành
social-listening để giảm khả năng một tài khoản bị khóa do vượt rate limit. Tuy nhiên:

- Đây bản chất là kỹ thuật né hệ thống chống gian lận/chống bot của nền tảng — vi phạm trực
  tiếp ToS của LinkedIn/Facebook, có thể dẫn tới khóa tài khoản hàng loạt hoặc rủi ro pháp lý
  (đặc biệt nếu dùng tài khoản thật của thành viên nhóm hoặc mua bán tài khoản ảo).
- Với quy mô một dự án MVP/học thuật, lợi ích (thêm 1 nguồn dữ liệu) không tương xứng với rủi ro
  (mất tài khoản, vi phạm điều khoản nền tảng, dữ liệu thu được không ổn định vì có thể bị chặn
  bất cứ lúc nào).
- Vì vậy tài liệu này dừng ở mức mô tả/phân tích, **không triển khai** account rotation hay bất
  kỳ cơ chế né tránh phát hiện nào. `LinkedInCollector`/nguồn Facebook (nếu thêm sau) sẽ tiếp
  tục là stub cho tới khi có hướng đi hợp lệ hơn.

## 3. Hướng đi đề xuất cho giai đoạn sau MVP

Ưu tiên theo thứ tự rủi ro tăng dần:

1. **API/đối tác chính thức** — LinkedIn Marketing Developer Platform (cần LinkedIn Page của
   chính công ty, chỉ đọc được dữ liệu Trang mình quản lý, không phải social listening rộng);
   Facebook Graph API cho Page riêng + Meta Content Library (dành cho nghiên cứu, cần đăng ký
   qua chương trình của Meta) là các lựa chọn tuân thủ ToS.
2. **Nhà cung cấp dữ liệu bên thứ ba có giấy phép** (ví dụ Brandwatch, Meltwater, Talkwalker...)
   — họ đã có thỏa thuận dữ liệu hợp pháp với nền tảng, chi phí cao hơn nhưng ổn định và không
   dính rủi ro ToS/pháp lý cho team.
3. **Thu thập thủ công/lấy mẫu có giới hạn** — với một tài khoản thật, truy cập ở tần suất
   giống người dùng thông thường (không tự động hóa hàng loạt), dùng cho việc lấy mẫu nhỏ phục
   vụ nghiên cứu định tính thay vì làm nguồn dữ liệu vận hành theo chu kỳ.
4. **Account rotation tự động** — chỉ cân nhắc nếu ở giai đoạn sau MVP có ngân sách cho hạ tầng
   proxy/tài khoản hợp lệ và chấp nhận rủi ro ToS đã nêu ở mục 2; không khuyến nghị cho phạm vi
   dự án hiện tại.

## 4. Tác động tới thiết kế hiện tại

- `sources.type` đã có sẵn giá trị enum `linkedin` (xem
  [docs/phase0/0.2-erd-foreign-keys.md](phase0/0.2-erd-foreign-keys.md)) nên khi có hướng đi khả
  thi, chỉ cần cài đặt lại `LinkedInCollector.collect()` — không cần đổi schema hay
  `runner.py`/`scheduler.py`.
- Facebook chưa có trong enum `source_type`; nếu triển khai sau, cần thêm giá trị `facebook` và
  một migration Alembic mới (không sửa migration `0001` đã áp dụng).

## 5. Cập nhật quyết định — Facebook qua Apify (ĐÃ TRIỂN KHAI)

Hướng đi cho Facebook (và các nguồn mạng xã hội phù hợp khác) đã CHỐT và TRIỂN KHAI là **dùng
Apify** — nhà cung cấp thu thập dữ liệu bên thứ ba, đúng hướng đi #2 đã đề xuất ở mục 3 ("Nhà cung
cấp dữ liệu bên thứ ba có giấy phép"). Cụ thể:

- Không tự scrape Facebook trực tiếp (giữ nguyên lo ngại về ToS/rủi ro khoá tài khoản đã phân
  tích ở mục 1-2 — vẫn đúng và vẫn là lý do KHÔNG chọn hướng tự scrape).
- `src/pipeline/collectors/apify_base.py::run_apify_actor_sync` — gọi thẳng REST API chính thức của
  Apify (`POST /v2/actors/:actorId/run-sync-get-dataset-items`) bằng `httpx` (không thêm dependency
  `apify-client` — REST API đơn giản, không cần SDK riêng). Rủi ro ToS/hạ tầng thu thập do Apify
  chịu trách nhiệm, hệ thống chỉ tiêu thụ dữ liệu qua API chính thức của họ.
- `src/pipeline/collectors/facebook.py::FacebookApifyCollector` — cùng interface
  `BaseCollector.collect()` như các collector hiện có (không đổi `base.py`/`get_collector()`).
  Mặc định dùng actor chính thức `apify/facebook-comments-scraper` để lấy COMMENT công khai trên
  bài đăng của 1 trang. `actor_id`/`run_input`/`field_map` đều cấu hình được qua `Source.config` —
  đổi sang actor khác (vd actor cho nhóm công khai, hoặc lấy bài đăng thay vì comment) không cần
  sửa code, chỉ cần actor mới trả JSON và khớp lại `field_map`.
- **CHỈ áp dụng cho trang/nhóm CÔNG KHAI.** Nhóm/trang riêng tư cần tài khoản đăng nhập — nằm ngoài
  phạm vi, giữ nguyên lo ngại đã nêu ở mục 2 (rủi ro dùng tài khoản thật/mua tài khoản).
- Đây là nguồn PHẢN HỒI KHÁCH HÀNG (comment khách hàng), đi vào bảng `posts` như
  google_play/app_store — KHÔNG phải nguồn đối chiếu (khác `bank_website`), chạy qua đúng
  Classification/Verification/Consensus hiện có.
- Incremental: Apify chạy actor như hộp đen (không tự early-stop theo `known_ids` như các collector
  khác) — collector tự lưu mốc thời gian chạy gần nhất vào `Source.config["since_date"]` qua cơ chế
  `resolved_config_update` sẵn có (giống cách app_store/google_play tự lưu app_id đã resolve), rồi
  truyền lại cho actor ở tham số ngày (mặc định `onlyCommentsNewerThan` của
  `apify/facebook-comments-scraper`) để hạn chế phải trả phí lấy lại dữ liệu cũ mỗi chu kỳ.
- **Chi phí:** Apify tính phí theo actor (thường theo số kết quả trả về, vd ~1.4 USD/1000 comment
  với actor mặc định) — cần `APIFY_API_TOKEN` hợp lệ và tài khoản Apify có credit. Collector luôn tự
  giới hạn `resultsLimit` mặc định (100) nếu `run_input` không tự đặt, tránh chạy không giới hạn.
- Migration `0013`: thêm giá trị enum `facebook` cho `source_type`.
- Setting mới: `apify_api_token` trong `src/config.py` (đọc từ `APIFY_API_TOKEN` trong `.env`) —
  để trống thì collector tự log cảnh báo và trả về rỗng, không chặn phần còn lại của hệ thống.
