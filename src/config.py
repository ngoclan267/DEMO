import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    # LLM (example chatbot in src/agents/)
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # LLM (Classification/Verification/Consensus/Pain Point agents in src/analysis/) — Google AI
    # Studio free-tier cấp quota RPM (request/phút)/TPM (token/phút)/RPD (request/ngày) RIÊNG cho
    # TỪNG model, không dùng chung 1 quota (đo thật trên dashboard tài khoản đang dùng, 2026-08-16):
    #   gemini-3.1-flash-lite : RPM 15 | TPM 250,000 | RPD 500    <- cân bằng nhất, dùng làm primary
    #   gemma-4-31b-it        : RPM 30 | TPM 16,000  | RPD 14,400 <- RPD cao nhất nhưng TPM THẤP —
    #                            Verification (call nặng nhất, ~2,213 token input trung bình, xem
    #                            query thật trên bảng llm_usage) chạm trần TPM ở ~7 lượt/phút, RẤT
    #                            SỚM so với trần RPM=30 (xem GEMINI_MODEL_RPM trong llm.py — dùng 7
    #                            làm RPM hiệu quả của model này, không phải 30)
    #   gemini-2.5-flash-lite : RPM 10 | TPM 250,000 | RPD 20     <- RPD quá thấp cho batch, chỉ
    #                            hứng vài lượt lẻ khi 2 model trên đã cạn quota trong ngày
    #   gemini-3.5-flash      : RPM 5  | TPM 250,000 | RPD 20     <- tương tự, dự phòng cuối cùng
    gemini_api_key: str = ""
    # Key BỔ SUNG từ các tài khoản Google KHÁC (CSV) — Google cấp quota RPM/TPM/RPD theo TỪNG
    # (api_key, model), không phải theo model không thôi, nên mỗi key thêm vào đây nhân bản gấp đôi
    # ngân sách thật của TOÀN BỘ chuỗi model ở trên (không chỉ 1 model). Để trống thì chỉ dùng
    # gemini_api_key, không đổi hành vi. Xem _gemini_api_keys()/_build_gemini_chain() trong
    # src/analysis/llm.py — luân phiên theo THỨ TỰ: hết mọi key của model hiện tại mới chuyển sang
    # model kế tiếp (ưu tiên tận dụng hết model tốt nhất trước khi hạ xuống model yếu hơn).
    gemini_extra_api_keys: str = ""
    analysis_model_name: str = "gemini-3.1-flash-lite"
    # Thứ tự LUÂN PHIÊN khi model đứng trước báo hết quota (429 RESOURCE_EXHAUSTED, xem
    # is_quota_error) — mỗi model có quota RIÊNG ở trên nên đây là dự phòng THẬT (model kế tiếp còn
    # nguyên quota), không phải retry vô ích trên cùng 1 quota đã cạn. Để trống thì chỉ dùng 1 mình
    # analysis_model_name, không luân phiên (xem _build_gemini_chain trong src/analysis/llm.py).
    analysis_fallback_model_names: str = "gemma-4-31b-it,gemini-3.5-flash,gemini-3.5-flash-lite"
    # Dự phòng CUỐI CÙNG khi TOÀN BỘ model Gemini/Gemma ở trên đều hết quota — trả phí nên không bị
    # giới hạn RPD như free-tier. Chỉ kích hoạt khi openai_api_key có giá trị; để trống thì hành vi
    # giữ nguyên như trước (chỉ dùng chuỗi Gemini/Gemma ở trên).
    openai_analysis_model_name: str = "gpt-4o-mini"

    # Hệ số an toàn nhân vào RPM THẬT của từng model (GEMINI_MODEL_RPM trong src/analysis/llm.py)
    # để tính nhịp gọi thật sự cho phép — chừa margin vì rate limiter đo theo thời gian thực, gọi
    # sát trần vẫn có thể trượt do độ trễ mạng/xử lý. Đặt theo TỶ LỆ (không phải số tuyệt đối như
    # analysis_rpm_limit trước đây) để KHÔNG còn phải tự tay đồng bộ lại mỗi khi đổi model — đây
    # chính là lỗi từng xảy ra: đổi analysis_model_name từ Gemma (RPM 30) sang gemini-3.1-flash-lite
    # (RPM 15) nhưng quên đổi số RPM giới hạn theo, khiến rate limiter cho phép gọi NHANH HƠN quota
    # thật của model mới -> vẫn dính 429. Giờ RPM thật tra theo đúng tên model đang dùng, tự động
    # đúng dù đổi analysis_model_name/analysis_fallback_model_names thế nào.
    analysis_rpm_safety_margin: float = Field(default=0.8, gt=0, le=1.0)
    # OpenAI fallback trả phí, hạn mức cao hơn Gemini free-tier rất nhiều — vẫn giới hạn để phòng
    # trường hợp fallback bị gọi dồn dập (vd Gemini lỗi hàng loạt cùng lúc), nhưng để mặc định cao
    # vì không phải nút thắt thật như Gemini free-tier.
    openai_rpm_limit: float = Field(default=450.0, gt=0)

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/painpoints"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    # Collector / Processing pipeline
    collection_interval_minutes: int = Field(default=15, ge=15, le=30)
    default_country: str = "vn"
    default_lang: str = "vi"

    # BankWebsiteCollector — tự nhận diện khi crawl trang công khai của ngân hàng (lịch sự, minh
    # bạch nguồn gốc request). Đổi được nếu 1 site chặn UA mặc định.
    bank_website_user_agent: str = "PainPointDiscoveryBot/1.0 (+official reference crawler)"

    # FacebookApifyCollector — dùng Apify (bên thứ ba) để lấy comment/bài đăng CÔNG KHAI trên
    # Facebook, KHÔNG tự scrape trực tiếp (xem docs/linkedin_facebook_scraping_research.md mục 5).
    # Để trống thì collector tự log cảnh báo và trả về rỗng (không chặn phần còn lại của hệ thống).
    apify_api_token: str = ""

    # Auth (JWT). Nếu không đặt SECRET_KEY trong .env, dùng key ngẫu nhiên mỗi lần khởi động
    # process (đủ cho dev; production nên đặt cố định để token không mất hiệu lực khi restart).
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60 * 24 * 7, ge=1)  # 7 ngày

    # Notification Service — email qua Brevo HTTP API (không dùng SMTP vì Railway chặn traffic
    # SMTP ra ngoài — xem docstring send_email() trong src/notifications/email.py).
    # brevo_sender_email PHẢI là địa chỉ đã "Verify a sender" trong Brevo dashboard, nếu không
    # Brevo từ chối gửi (trả lỗi 401/400) dù api-key đúng.
    brevo_api_key: str = ""
    brevo_sender_email: str = ""

    # Frontend — dùng để build link trong email (vd link reset password)
    frontend_base_url: str = "http://localhost:3000"
    # Backend — URL công khai gọi tới được của chính server này, dùng để build vnp_ReturnUrl (VNPay
    # redirect trình duyệt về đây sau khi thanh toán). Khác frontend_base_url vì đây là API, không
    # phải trang web.
    backend_base_url: str = "http://localhost:8000"

    # Dùng thử + thanh toán VNPay cho tài khoản doanh nghiệp do platform admin tạo (xem
    # src/billing/vnpay.py, src/api/routes_billing.py). Để trống vnpay_tmn_code/vnpay_hash_secret
    # thì tính năng thanh toán tự báo lỗi rõ ràng "chưa cấu hình", không crash — giống apify_api_token.
    trial_duration_days: int = Field(default=14, ge=1)
    # Trần SỐ LƯỢT GỌI AI (llm_usage) miễn phí cho tài khoản "dùng thử" — hết trần này thì tạm dừng
    # phân tích thêm y hệt hết hạn theo THỜI GIAN (trial_ends_at), chỉ khác điều kiện kích hoạt
    # (KHÔNG khoá đăng nhập, chỉ hiện banner mời nâng cấp — xem UserResponse.trial_expired,
    # _trial_users_blocked_from_analysis trong src/analysis/runner.py). Đo bằng SỐ LƯỢT GỌI, không
    # phải $ chi phí ước tính: model đang
    # cấu hình (analysis_model_name = gemma-4-26b-a4b-it) MIỄN PHÍ nên trần theo $ sẽ không bao giờ
    # kích hoạt cho tới khi đổi sang model trả phí, trong khi trần theo số lượt phản ánh đúng khối
    # lượng dịch vụ đã dùng bất kể model nào đang chạy phía sau. 1000 lượt ≈ vài trăm phản hồi khách
    # hàng được phân tích đầy đủ (mỗi phản hồi tốn 2-3 lượt: classify + verify + đôi khi consensus
    # reasoning) — mốc khởi điểm hợp lý cho 1 đợt dùng thử có ý nghĩa, nên tinh chỉnh lại theo dữ
    # liệu thật quan sát được ở trang /admin/users.
    trial_analysis_call_limit: int = Field(default=100_000, ge=1)
    # Trần lượt gọi AI miễn phí TRONG 1 NGÀY (UTC) cho tài khoản dùng thử — TÁCH BIỆT với trần TRỌN
    # ĐỜI ở trên: trần ngày KHÔNG khoá đăng nhập, chỉ tạm dừng phân tích thêm cho tài khoản đó tới
    # khi qua ngày mới (xem _trial_users_blocked_from_analysis trong src/analysis/runner.py), đồng thời
    # hiện banner "hết lượt hôm nay" trên dashboard (xem trial_daily_call_limit trong
    # UserResponse/routes_auth.py::get_me). Mặc định 50 ≈ 1/20 trần trọn đời — đủ để hiểu tình hình
    # dữ liệu thay đổi hàng ngày mà không cho phép dùng thử "cày" hết cả trần trọn đời chỉ trong 1
    # ngày rồi bỏ đi.
    trial_daily_call_limit: int = Field(default=50, ge=1)
    # Trần số BẢN GHI THÔ được THU THẬP MỚI mỗi ngày (UTC) cho tài khoản dùng thử — khác hẳn 2 trần
    # ở trên (đó giới hạn khâu PHÂN TÍCH bằng AI), đây giới hạn khâu THU THẬP (Collector Agent, xem
    # _trial_daily_crawl_remaining trong src/pipeline/runner.py). Không giới hạn thì tài khoản dùng
    # thử có thể backfill hàng nghìn review ngay ngày đầu (BACKFILL_LIMIT_PER_SOURCE=2000/nguồn) —
    # thấy gần hết dữ liệu miễn phí ngay từ đầu thì không còn động lực nâng cấp. Tính GỘP mọi loại dữ
    # liệu (review + tài liệu đối chiếu) của TOÀN BỘ topic mà user đó sở hữu, không tách theo từng
    # nguồn — "1 tài khoản = 1 ngân sách", giống trial_daily_call_limit.
    #
    # 200 CỐ Ý cao hơn hẳn năng lực phân tích thật trong ngày (trial_daily_call_limit=50 lượt gọi ≈
    # 17-25 phản hồi phân tích được) — tạo đúng hiệu ứng "đã thu thập được nhiều nhưng chưa phân tích
    # kịp", là lý do nâng cấp thuyết phục nhất (thấy rõ dữ liệu đang chờ, không phải chỉ nghe nói).
    # Thấp quá thì thu thập tự nó đã là nút thắt, không kịp tới lượt phân tích để thấy giới hạn đó;
    # cao quá thì mất cảm giác giới hạn. Tinh chỉnh lại theo dữ liệu chuyển đổi thật khi có.
    trial_daily_crawl_limit: int = Field(default=200, ge=1)
    subscription_price_vnd: int = Field(default=2_000_000, ge=1000)
    vnpay_tmn_code: str = ""
    vnpay_hash_secret: str = ""
    # URL sandbox mặc định — đổi sang URL production (pay.vnpay.vn) khi triển khai thật.
    vnpay_payment_url: str = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"


@lru_cache
def get_settings() -> Settings:
    return Settings()
