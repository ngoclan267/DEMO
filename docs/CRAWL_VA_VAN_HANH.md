# Crawl dữ liệu & Vận hành hệ thống Social Listening

> Tài liệu này mô tả **thực tế những gì code đang làm** (không phải kế hoạch), dựa trên
> `src/agents/tools/crawlers/`, `src/agents/`, `src/api/routes.py`, `src/scheduler.py`,
> `src/db/repository.py`, `frontend/index.html`. Xem thêm bức tranh tổng thể ở
> [architecture_diagram.md](./architecture_diagram.md) và đặc tả nghiệp vụ ở `PRD.md`.

## 1. Tổng quan một chu kỳ

```
Nguồn thật (Google Play / App Store / Facebook / Instagram)
        │
        ▼
  Collector Agent  ──▶  Processing Agent  ──▶  Classification Agent (LLM)
        │                                             │
        ▼                                             ▼
   SQLite (Post)                              negative_predictions
                                                       │
                                                       ▼
                                            Verification Agent (LLM)
                                                       │
                                                       ▼
                                              Consensus Agent
                                                       │
                                                       ▼
                                             Pain Point Agent  ──▶  SQLite (PainPoint)
                                                       │
                                                       ▼
                                           Notification Service ──▶  SQLite (Notification)
```

Toàn bộ luồng trên được ghép thành một `StateGraph` của LangGraph trong
[src/agents/graph.py](../src/agents/graph.py), state dùng chung khai báo ở
[src/agents/state.py](../src/agents/state.py). Một lần chạy hết graph = **một chu kỳ pipeline
cho một Topic** (một ngân hàng/thương hiệu đang theo dõi), mất khoảng 15–30 phút theo PRD.

Chu kỳ này được kích hoạt theo 2 cách:
- **Tự động**: `BackgroundScheduler` (APScheduler) trong [src/scheduler.py](../src/scheduler.py)
  chạy `run_all_topics()` mỗi `PIPELINE_INTERVAL_MINUTES` phút (mặc định 20, xem `src/config.py`),
  lặp qua tất cả Topic trong DB.
- **Thủ công**: gọi `POST /api/v1/topics/{topic_id}/run-pipeline` (xem mục 4).

## 2. Cách crawl dữ liệu

Toàn bộ logic nằm ở `src/agents/tools/crawler_tools.py` (điều phối) và
`src/agents/tools/crawlers/*.py` (crawler riêng cho từng nguồn). Nguyên tắc xuyên suốt được
ghi rõ trong code: **chỉ dùng nguồn công khai/chính thức, không đăng nhập giả, không xoay tài
khoản, không né cơ chế chống bot** — nếu thiếu cấu hình hoặc nguồn chưa hỗ trợ, trả về danh
sách rỗng và log cảnh báo thay vì tạo dữ liệu giả.

Mỗi Topic có `sources: list[str]` và `source_configs: dict[str, dict]` (xem
`TopicCreate` trong `src/models/schemas.py`). Collector Agent
([src/agents/nodes/collector.py](../src/agents/nodes/collector.py)) lặp qua từng `source` của
Topic, lấy config tương ứng và gọi `crawl_source(source, keywords, topic_id, source_config)`.

### 2.1 Google Play (`google_play`)

- File: [google_play.py](../src/agents/tools/crawlers/google_play.py)
- Dùng thư viện `google-play-scraper` (đọc trực tiếp trang review công khai của Google Play,
  không cần đăng nhập).
- Config bắt buộc: `{"app_id": "vn.com.techcombank.bb.app"}` (package name thật trên Play Store).
- Lấy review **mới nhất trước** (`Sort.NEWEST`), phân trang qua `continuation_token` để đào sâu
  vào lịch sử thay vì chỉ lấy 40 review mới nhất mỗi lần — nếu không, dữ liệu gần như đứng yên
  qua mỗi chu kỳ crawl.
- Dừng lại khi: đủ `max_total` (mặc định 300 review/chu kỳ), hết dữ liệu (token rỗng hoặc 1
  trang trả về 0 kết quả), hoặc Google chặn (bắt exception và dừng, không crash pipeline).

### 2.2 App Store (`app_store`)

- File: [app_store.py](../src/agents/tools/crawlers/app_store.py)
- Dùng RSS Customer Reviews chính thức của Apple (không cần đăng nhập, không vi phạm ToS):
  `https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortby=mostrecent/json`
- Config bắt buộc: `{"app_id": "1548623362", "country": "vn"}` (App Store numeric id).
- RSS phân trang ~50 review/trang, tối đa 10 trang chính thức của Apple; crawler lặp qua các
  trang cho đến khi trang trả về rỗng hoặc chạm `max_pages`.

### 2.3 Facebook / Instagram (`facebook`, `instagram`)

- File: [meta_graph.py](../src/agents/tools/crawlers/meta_graph.py)
- Dùng **Meta Graph API chính thức** — giới hạn thật của nền tảng (không phải giới hạn kỹ
  thuật): Graph API chỉ trả về dữ liệu của **Page / Instagram Business account mà chính doanh
  nghiệp sở hữu và quản trị**. Không thể "crawl" bình luận/bài viết công khai từ trang khác theo
  từ khóa tự do như Google Play/App Store.
- Config bắt buộc:
  - `facebook`: `{"page_id": "...", "access_token": "..."}` (Page Access Token với quyền
    `pages_read_engagement`).
  - `instagram`: `{"ig_user_id": "...", "access_token": "..."}` (Instagram Business/Creator
    account liên kết Facebook Page, quyền `instagram_basic`, `instagram_manage_comments`).
- Cơ chế: lấy feed bài viết/media gần đây của Page/account, sau đó lấy comment của từng bài.
- Nếu thiếu `access_token` → raise `RuntimeError`, được `crawl_source()` bắt lại thành danh
  sách rỗng + log cảnh báo (không crash pipeline).

### 2.4 LinkedIn (`linkedin`)

**Chưa triển khai crawler thật.** LinkedIn hạn chế rất chặt việc truy cập nội dung công khai
qua API/scraping với bên thứ ba. Giá trị `"linkedin"` trong `Topic.sources` được giữ lại cho lộ
trình sau này (khi có đối tác API); hiện tại `crawl_source()` sẽ log cảnh báo và trả về rỗng.

### 2.5 Khử trùng lặp giữa các chu kỳ

Vì các crawler **không có con trỏ "since"** (Google Play/App Store trả lại phần lớn review cũ
mỗi lần gọi), việc lọc trùng được xử lý ở 2 lớp trong
[src/agents/nodes/processing.py](../src/agents/nodes/processing.py) và
[src/db/repository.py](../src/db/repository.py):

1. **Trong cùng 1 lần crawl**: loại trùng theo nội dung đã chuẩn hoá (lowercase, strip khoảng
   trắng) bằng một `seen set`.
2. **Với dữ liệu đã lưu ở các chu kỳ trước**: `filter_new_posts()` so khớp
   `sha256(topic_id|source|content)` với cột `content_hash` đã tồn tại trong SQLite — review cũ
   crawl lại sẽ bị loại trước khi vào Classification/Pain Point, tránh đếm trùng `post_count`.

## 3. Pipeline phân tích (sau khi đã có Post thô)

Mỗi node là một hàm thuần nhận/trả một phần của `AgentState`
([src/agents/state.py](../src/agents/state.py)):

| Node | File | Việc làm |
|---|---|---|
| `collector` | `nodes/collector.py` | Gọi crawler theo mục 2, trả `raw_posts`. |
| `processing` | `nodes/processing.py` | Khử trùng lặp, chuẩn hoá khoảng trắng, lọc bản ghi đã lưu trước đó → `clean_posts`. |
| `classification` | `nodes/classification.py` | Gọi LLM (`classify_post`) để gán sentiment/topic_label/severity_score/confidence_score cho từng post → `predictions`, lọc ra `negative_predictions` (sentiment=negative và severity ≥ 0.5). |
| `verification` | `nodes/verification.py` | Với từng tín hiệu tiêu cực, gọi LLM (`verify_negative_signal`) để đối chiếu xem đây có phải lỗi đã xác nhận chính thức hay chưa đủ căn cứ → `verifications`. |
| `consensus` | `nodes/consensus.py` | So khớp kết quả Classification và Verification; nếu mâu thuẫn thì hạ độ tin cậy và đánh dấu cần xem xét thêm → `consensus_results`. |
| `pain_point` | `nodes/pain_point.py` | Gom các phản hồi tiêu cực theo `topic_label` (7 nhóm cố định: đăng nhập, giao dịch, bảo mật, nhân viên, dịch vụ, ứng dụng, chính sách) thành từng `PainPoint`, kèm vài phản hồi mẫu thật (`sample_posts`) để người dùng đối chiếu. |
| `notification` | `nodes/notification.py` | Nếu `post_count` của một Pain Point vượt `NEGATIVE_ALERT_THRESHOLD` (mặc định 10), tạo `Notification`. |

**Classification/Verification Agent** (`src/services/llm_service.py`) gọi **Google Gemini**
(`gemini_api_key`, `llm_model` trong `.env`). Nếu không có API key hoặc gọi lỗi, tự động
fallback về heuristic dựa trên từ khóa tiếng Việt (có dấu và không dấu) để pipeline vẫn chạy
hết end-to-end mà không fabricate kết quả ngẫu nhiên vô căn cứ.

Kết quả cuối (`raw_posts`, `predictions`, `pain_points`, `notifications`) được
[src/services/pipeline_runner.py](../src/services/pipeline_runner.py) ghi vào SQLite qua
`src/db/repository.py`:
- Post mới được lưu (bỏ qua bản ghi trùng `content_hash`).
- Pain Point cùng `topic_id + title` từ chu kỳ trước được **gộp** (cộng dồn `post_count`, lấy
  severity cao nhất, hợp nhất `sample_posts`/`sources`) thay vì tạo bản ghi rời rạc mỗi chu kỳ —
  nếu không, cùng một vấn đề sẽ bị vụn vặt thành nhiều Pain Point nhỏ theo thời gian.
- Một Pain Point đã đánh dấu "đã xử lý" (`resolved`) nhưng chu kỳ mới lại phát hiện thêm phản
  hồi tiêu cực cùng nhóm sẽ **tự mở lại** (`status → open`).

## 4. Web vận hành như thế nào

### 4.1 Backend (FastAPI)

Entry point: [src/main.py](../src/main.py).

- Khi start: `lifespan()` gọi `init_and_seed()` (tạo bảng SQLite nếu chưa có, seed 5 Topic ngân
  hàng thật với `app_id` đã xác minh trên Google Play/App Store — Techcombank, Vietcombank, MB
  Bank, SHB, TPBank) rồi `start_scheduler()` (bật auto-crawl, có thể tắt bằng
  `ENABLE_SCHEDULER=false` trong `.env`, dùng khi chạy test để không crawl mạng thật).
- Router chính ở [src/api/routes.py](../src/api/routes.py), mount dưới prefix `/api/v1`.
- CORS mở toàn bộ (`allow_origins=["*"]`) để frontend tĩnh gọi thẳng vào API.
- Lưu trữ: SQLite đồng bộ (`data/social_listening.db`, qua SQLAlchemy) — độc lập với
  `DATABASE_URL` (Postgres) khai báo cho hướng production sau này trong `docker-compose.yml`.

Các endpoint chính (đầy đủ tag/docstring xem trực tiếp `src/api/routes.py`, hoặc `/docs` khi
server chạy):

| Method & path | Việc làm |
|---|---|
| `GET /api/v1/topics` | Danh sách Topic (thương hiệu) đang theo dõi. |
| `POST /api/v1/topics` | Tạo Topic mới (tên, từ khoá, nguồn, `source_configs`, ngưỡng cảnh báo). |
| `GET /api/v1/topics/{id}` | Chi tiết 1 Topic. |
| `GET /api/v1/topics/{id}/pain-points` | Danh sách Pain Point (dashboard) của Topic. |
| `GET /api/v1/topics/{id}/posts` | Danh sách review/phản hồi **thật** đã crawl được. |
| `GET /api/v1/topics/{id}/trend` | Xu hướng phản hồi tiêu cực theo ngày (zero-filled). |
| `GET /api/v1/pain-points/{id}` | Chi tiết 1 Pain Point. |
| `PATCH /api/v1/pain-points/{id}` | Cập nhật trạng thái xử lý/người phụ trách/ghi chú (thao tác nghiệp vụ của con người, không phải output của agent). |
| `GET /api/v1/report/summary` | KPI tổng hợp cross-topic (SLA, thời gian xử lý trung bình…). |
| `GET /api/v1/notifications` | Lịch sử thông báo trên tất cả Topic. |
| `POST /api/v1/topics/{id}/run-pipeline` | Kích hoạt thủ công 1 chu kỳ pipeline thật cho Topic. |
| `GET /api/v1/health` | Health check. |

### 4.2 Scheduler tự động

[src/scheduler.py](../src/scheduler.py) dùng `apscheduler.BackgroundScheduler` (thread riêng vì
toàn bộ pipeline là code đồng bộ — `httpx`, `google-play-scraper`, SQLAlchemy sync — để không
chặn event loop async của FastAPI). Job `auto_crawl_pipeline` chạy ngay 1 lần lúc khởi động, sau
đó lặp lại mỗi `PIPELINE_INTERVAL_MINUTES` phút, gọi `run_pipeline_for_topic()` tuần tự cho từng
Topic trong DB (`max_instances=1`, `coalesce=True` để không chạy chồng lấn nếu 1 chu kỳ kéo dài
hơn interval).

### 4.3 Frontend

[frontend/index.html](../frontend/index.html) là một trang tĩnh (SPA thuần JS, không build step,
~1700 dòng) chứa cả các màn hình: Workspace, Dashboard theo Topic, chi tiết Pain Point, Trung
tâm thông báo, Report/Command Center.

- Khi load, `resolveApiBase()` thử lần lượt `window.location.origin`, `http://127.0.0.1:8000`,
  `http://localhost:8000`, gọi `/api/v1/health` để tự dò ra backend đang chạy ở đâu — nhờ vậy
  frontend tĩnh có thể mở trực tiếp bằng file hoặc qua Nginx mà không cần hard-code URL.
- Mọi thao tác trên UI (xem Pain Point, đổi trạng thái, xem review gốc…) đều gọi thẳng REST API
  ở mục 4.1 qua hàm `apiFetch()`, không có state phía server riêng cho frontend.

### 4.4 Triển khai (Docker)

`docker-compose.yml` định nghĩa 3 service:
- `api`: build từ `Dockerfile`, chạy FastAPI ở cổng 8000, đọc biến môi trường từ `.env.example`.
- `db`: Postgres 16 (dự phòng cho `DATABASE_URL`/hướng production; pipeline hiện tại vẫn ghi
  thẳng vào SQLite file trong container, xem lưu ý ở mục 4.1).
- `frontend`: Nginx phục vụ tĩnh nội dung thư mục `frontend/`, cổng 3000.

### 4.5 Biến môi trường quan trọng (`.env`)

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `GEMINI_API_KEY` | API key Google Gemini cho Classification/Verification Agent | rỗng → fallback heuristic |
| `LLM_MODEL` | Model Gemini dùng để phân loại | `gemini-2.5-flash` |
| `PIPELINE_INTERVAL_MINUTES` | Chu kỳ auto-crawl | `20` |
| `NEGATIVE_ALERT_THRESHOLD` | Số phản hồi tiêu cực/Pain Point trước khi gửi thông báo | `10` |
| `ENABLE_SCHEDULER` | Bật/tắt auto-crawl (tắt khi chạy test) | `true` |
| `SQLITE_PATH` | Đường dẫn file SQLite lưu dữ liệu thật | `data/social_listening.db` |
| `SLA_RESPONSE_HOURS` | Mốc SLA xử lý Pain Point, dùng cho `GET /report/summary` | `48` |

## 5. Hướng dẫn chạy web từng bước

### Cách A — Chạy trực tiếp bằng Python (khuyến nghị khi phát triển)

1. **Cài Python 3.11+** (Dockerfile dùng `python:3.11-slim`, nên dùng cùng bản để tránh lệch
   phiên bản thư viện).

2. **Tạo và kích hoạt virtualenv** (thư mục `.venv` đã có sẵn trong repo; nếu tạo mới):

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. **Cài dependencies:**

   ```powershell
   pip install -r requirements.txt
   # nếu cần chạy test/lint:
   pip install -r requirements-dev.txt
   ```

4. **Tạo file `.env`** (copy từ `.env.example` rồi điền giá trị thật):

   ```powershell
   Copy-Item .env.example .env
   ```

   Các biến đáng chú ý (đầy đủ ở mục 4.5):
   - `GEMINI_API_KEY` — để trống thì Classification/Verification Agent tự fallback sang
     heuristic từ khoá (vẫn chạy được, không cần key để demo).
   - `ENABLE_SCHEDULER=false` — đặt nếu muốn tắt auto-crawl mạng thật (ví dụ khi chỉ đang code
     UI, không muốn tốn quota Google Play/App Store).
   - `SQLITE_PATH=data/social_listening.db` — nơi lưu dữ liệu thật, giữ mặc định là được (file
     `data/social_listening.db` đã tồn tại sẵn trong repo).

5. **Chạy server API:**

   ```powershell
   python -m src.main
   ```

   hoặc tương đương bằng uvicorn trực tiếp:

   ```powershell
   uvicorn src.main:app --reload --port 8000
   ```

   Lần đầu chạy, `lifespan()` sẽ tự tạo bảng SQLite và seed 5 Topic ngân hàng thật (Techcombank,
   Vietcombank, MB Bank, SHB, TPBank), đồng thời bật scheduler chạy pipeline crawl lần đầu ngay
   lập tức (trừ khi `ENABLE_SCHEDULER=false`).

6. **Kiểm tra API đã chạy:**

   ```powershell
   curl http://127.0.0.1:8000/api/v1/health
   ```

   Xem tài liệu API tương tác (Swagger) tại `http://127.0.0.1:8000/docs`.

7. **Mở frontend:** mở trực tiếp file [frontend/index.html](../frontend/index.html) bằng trình
   duyệt (double-click hoặc `start frontend/index.html`), hoặc phục vụ qua server tĩnh bất kỳ.
   Trang sẽ tự dò ra `http://127.0.0.1:8000` (xem `resolveApiBase()` ở mục 4.3) nên không cần
   cấu hình URL thủ công.

8. **(Tuỳ chọn) Kích hoạt crawl thủ công cho 1 Topic** thay vì đợi scheduler:

   ```powershell
   $topics = (Invoke-RestMethod http://127.0.0.1:8000/api/v1/topics)
   Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/v1/topics/$($topics[0].id)/run-pipeline"
   ```

9. **Chạy test (tuỳ chọn):**

   ```powershell
   pytest
   ```

   `tests/conftest.py` tự đặt `ENABLE_SCHEDULER=false` khi test nên sẽ không crawl mạng thật.

### Cách B — Chạy bằng Docker Compose (gần với production hơn)

1. Đảm bảo Docker Desktop đang chạy.
2. Điền `GEMINI_API_KEY` (và các biến khác nếu cần) vào `.env.example` — `docker-compose.yml`
   nạp trực tiếp file này làm `env_file` cho service `api`.
3. Build và chạy:

   ```powershell
   docker compose up --build
   ```

   Lệnh này khởi động 3 container: `api` (FastAPI, cổng 8000), `db` (Postgres, cổng 5432, dự
   phòng cho hướng production), `frontend` (Nginx phục vụ `frontend/index.html`, cổng 3000).
4. Truy cập:
   - Frontend: `http://localhost:3000`
   - API: `http://localhost:8000` (docs: `http://localhost:8000/docs`)
5. Dừng hệ thống: `Ctrl+C` rồi `docker compose down` (thêm `-v` nếu muốn xoá luôn volume
   `pgdata`).

   > Lưu ý: pipeline crawl/lưu dữ liệu thật hiện vẫn ghi vào **SQLite bên trong container `api`**
   > (`data/social_listening.db`), không phải vào Postgres — container Postgres trong compose là
   > chuẩn bị cho hướng production sau này (`DATABASE_URL`), chưa được pipeline hiện tại sử dụng.
   > Vì vậy nếu container `api` bị xoá/rebuild mà không mount volume cho `data/`, dữ liệu crawl
   > được sẽ mất.

## 6. Giới hạn có chủ đích của MVP

- Không có cơ chế "xoay tài khoản" hay né chống bot cho bất kỳ nguồn nào — đây là giới hạn có
  chủ đích, không phải thiếu sót (xem đầu file `crawler_tools.py`).
- Facebook/Instagram chỉ giám sát được Page/account mà chính doanh nghiệp sở hữu, không crawl
  được nội dung công khai của bên khác theo từ khóa.
- LinkedIn: chưa có crawler thật.
- Nếu thiếu `source_config` hợp lệ cho một nguồn, hệ thống trả về danh sách rỗng + log cảnh báo,
  tuyệt đối không tự sinh dữ liệu giả để lấp đầy dashboard.
