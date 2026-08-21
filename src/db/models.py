import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def gen_uuid():
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    # Tên đăng nhập: đăng nhập được bằng username HOẶC email. Nullable vì các tài khoản tạo trước
    # khi có tính năng này không có username (Postgres cho phép nhiều NULL trong cột UNIQUE) —
    # form đăng ký trên web thì bắt buộc nhập.
    username = Column(String(30), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    # Xác thực email khi đăng ký — chặn đăng nhập cho tới khi bấm link trong email (xem
    # routes_auth.py). Tài khoản tạo trước tính năng này được backfill is_verified=True (migration
    # 0007) nên không bị khoá đột ngột.
    is_verified = Column(Boolean, nullable=False, default=False)
    verification_token = Column(String(255), nullable=True)
    verification_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    # Quản trị TỔNG nền tảng — khác chủ sở hữu topic (chỉ quản lý 1 workspace riêng). Cho phép tạo
    # topic THAY doanh nghiệp khác kèm tạo luôn tài khoản chủ sở hữu cho họ (xem POST /topics/admin).
    is_platform_admin = Column(Boolean, nullable=False, default=False)
    # Dùng thử/đã thanh toán — chỉ áp dụng cho tài khoản tạo ở chế độ "dùng thử" (plan="trial" qua
    # POST /topics/admin, xem routes_topics.py::admin_create_topic). Mặc định True để tài khoản
    # chính thức (plan="paid"), tài khoản nhân viên tự tạo (add_member) hay tài khoản demo không vô
    # tình bị áp trần dùng thử. Hết hạn trial_ends_at (hoặc hết trần trọn đời
    # trial_analysis_call_limit) mà is_paid vẫn False KHÔNG khoá đăng nhập — chỉ tạm dừng phân tích
    # thêm (xem _trial_users_blocked_from_analysis trong src/analysis/runner.py) và hiện banner mời
    # nâng cấp (UserResponse.trial_expired, xem routes_auth.py::_build_user_response).
    is_paid = Column(Boolean, nullable=False, default=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    topics = relationship("Topic", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")


class TopicMember(Base):
    """Đồng nghiệp được chủ sở hữu mời vào chủ đề — cho phép xem dashboard và xử lý case, nhưng
    KHÔNG được sửa/xoá chủ đề hay quản lý thành viên (xem src/api/deps.py). Chủ sở hữu là
    Topic.user_id, ngầm định có mọi quyền, không cần dòng riêng ở bảng này."""

    __tablename__ = "topic_members"

    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # Phòng ban của nhân viên NÀY trong CHỦ ĐỀ (ngân hàng) này — text tự do như PainPoint.department
    # (lý do tương tự: cơ cấu phòng ban của từng ngân hàng hay đổi, không đáng 1 migration mỗi lần).
    # Nguồn để Topic.auto_assign_enabled chọn phòng ban phù hợp khi tự động phân việc (xem
    # src/analysis/department_routing.py) — 1 người có thể ở phòng ban khác nhau tuỳ chủ đề/ngân
    # hàng đang tham gia, nên đặt ở đây thay vì User (không phải thuộc tính toàn cục của tài khoản).
    department = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    topic = relationship("Topic", back_populates="members")
    user = relationship("User")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    keywords = Column(JSONB, nullable=False, default=list)
    alert_threshold = Column(Integer, nullable=False, default=10)
    notify_enabled = Column(Boolean, nullable=False, default=True)
    notify_channel = Column(Enum("email", "web", "both", name="notify_channel_type"), nullable=False, default="both")
    status = Column(Enum("active", "archived", name="topic_status"), nullable=False, default="active")
    # Tự động gán PHÒNG BAN (không chọn người cụ thể) cho pain point mới dựa trên độ phù hợp nội
    # dung, xem src/analysis/department_routing.py::auto_route_pain_point — gọi từ
    # run_pain_point_agent() ngay sau khi upsert pain point, cùng cách check_and_notify() đang gate
    # theo notify_enabled. Mặc định TẮT (khác notify_enabled mặc định bật) vì đây là hành vi tự
    # động GHI DỮ LIỆU xử lý việc, cần ngân hàng chủ động bật, không nên âm thầm đổi hành vi hiện có.
    auto_assign_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="topics")
    members = relationship("TopicMember", back_populates="topic", cascade="all, delete-orphan")
    sources = relationship("Source", back_populates="topic", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="topic", cascade="all, delete-orphan")
    pain_points = relationship("PainPoint", back_populates="topic", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="topic", cascade="all, delete-orphan")
    official_documents = relationship("OfficialDocument", back_populates="topic", cascade="all, delete-orphan")


class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    # "bank_website": nguồn ĐỐI CHIẾU (thông báo/chính sách/biểu phí/sự cố/bảo trì/sản phẩm chính
    # thức của ngân hàng) — khác hẳn các loại còn lại (đều là phản hồi khách hàng). Xem
    # REFERENCE_SOURCE_TYPES trong src/pipeline/collectors/__init__.py để biết runner tách nhánh xử
    # lý ra sao (đi vào bảng official_documents, không vào posts).
    # "facebook": comment/bài đăng công khai trên Facebook, thu thập qua Apify (bên thứ ba) — xem
    # FacebookApifyCollector. Là phản hồi khách hàng, đi vào posts như google_play/app_store.
    type = Column(
        Enum(
            "google_play", "app_store", "linkedin", "bank_website", "facebook", "news_article", "tiktok", name="source_type"
        ),
        nullable=False,
    )
    config = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    # Lịch crawl riêng cho nguồn này — NULL nghĩa là dùng nhịp scheduler mặc định (hành vi cũ, không
    # đổi cho mọi source hiện có). Có giá trị thì _is_source_due() trong runner.py chỉ crawl lại khi
    # đã đủ lâu kể từ last_crawled_at — cần cho các nguồn ít thay đổi (vd website ngân hàng) để không
    # gọi lại mỗi 15-30 phút như review.
    crawl_interval_minutes = Column(Integer, nullable=True)
    last_crawled_at = Column(DateTime(timezone=True), nullable=True)
    # Trọng số ưu tiên phân tích — mặc định 1 nghĩa là MỌI nguồn ngang nhau (round-robin đều, xem
    # rank_within_source trong src/analysis/runner.py). Số lớn hơn được xếp vào batch phân tích
    # thường xuyên hơn theo ĐÚNG TỶ LỆ (vd priority=3 được chọn nhiều gấp 3 lần priority=1), nhưng
    # KHÔNG BAO GIỜ về 0 lượt — khác hẳn thứ tự cứng "xong nguồn A mới tới nguồn B" (cách đó tái
    # tạo lại đúng lỗi 1 nguồn backlog khổng lồ chiếm hết batch mà cơ chế round-robin đã sửa).
    analysis_priority = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    topic = relationship("Topic", back_populates="sources")
    posts = relationship("Post", back_populates="source")
    official_documents = relationship("OfficialDocument", back_populates="source")


class OfficialDocument(Base):
    """Tài liệu tham chiếu CHÍNH THỨC (thông báo/chính sách/biểu phí/sự cố/bảo trì/sản phẩm) thu
    thập từ website ngân hàng — làm nguồn đối chiếu cho Verification Agent (xem
    src/analysis/knowledge_base/loader.py::load_topic_documents). Đây KHÔNG phải phản hồi khách hàng
    nên tách hẳn khỏi Post/Prediction/PainPoint — không tham gia clustering/SLA/pain point.

    Riêng category="news" (tin bên thứ ba, qua NewsApifyCollector) có thêm `sentiment` — sắc thái
    ĐƯA TIN về doanh nghiệp (tích cực/trung lập/tiêu cực), tính bởi News Sentiment Agent (xem
    src/analysis/news_classification.py), KHÔNG đi qua Classification/Verification/Consensus đầy đủ
    như Post (không cần topic_label/severity/đối chiếu chính sách — chỉ cần biết truyền thông đang
    nói gì). Luôn NULL với category khác "news"."""

    __tablename__ = "official_documents"
    __table_args__ = (UniqueConstraint("topic_id", "url", name="uq_official_documents_topic_url"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    category = Column(
        Enum("notice", "policy", "fee", "incident", "maintenance", "product", "news", "other", name="document_category"),
        nullable=False,
        default="other",
    )
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    content = Column(Text, nullable=True)
    # sha256 của content — phát hiện nội dung trang đã đổi giữa các lần crawl (vd biểu phí cập nhật)
    # mà không phải so sánh chuỗi dài mỗi lần upsert.
    content_hash = Column(String(64), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    first_seen_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    # Sắc thái đưa tin — CHỈ News Sentiment Agent điền cho category="news" (xem docstring lớp này ở
    # trên); NULL với mọi category khác (tài liệu chính thức của ngân hàng không có "sắc thái đưa
    # tin", đó là văn bản gốc của chính doanh nghiệp). Dùng chung enum "sentiment_type" với
    # Prediction.sentiment — cùng ý nghĩa positive/neutral/negative, không cần enum riêng.
    sentiment = Column(Enum("positive", "neutral", "negative", name="sentiment_type"), nullable=True)
    sentiment_classified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    topic = relationship("Topic", back_populates="official_documents")
    source = relationship("Source", back_populates="official_documents")


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_posts_source_external_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    external_id = Column(String(255), nullable=True)
    raw_content = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    language = Column(String(10), nullable=False, default="vi")
    posted_at = Column(DateTime(timezone=True), nullable=True)
    collected_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    # Phản hồi của nhà phát triển/ngân hàng cho review này — hiện chỉ Google Play có (App Store RSS
    # feed công khai không trả về). NULL nghĩa là chưa có phản hồi (hoặc nguồn không hỗ trợ), không
    # phải "chưa thu thập được". Có thể được cập nhật ở lần upsert sau nếu ban đầu chưa có phản hồi
    # rồi ngân hàng mới trả lời (xem upsert_posts trong src/pipeline/processing/dedup.py).
    reply_content = Column(Text, nullable=True)
    reply_at = Column(DateTime(timezone=True), nullable=True)
    is_duplicate = Column(Boolean, nullable=False, default=False)
    is_spam = Column(Boolean, nullable=False, default=False)
    status = Column(Enum("raw", "cleaned", name="post_status"), nullable=False, default="raw")
    # Số liệu tương tác — hiện chỉ FacebookApifyCollector điền (xem
    # src/pipeline/collectors/facebook.py), NULL với mọi nguồn khác (Google Play/App Store không có
    # khái niệm like/share, chỉ có rating — đã có priority_score/severity_score riêng).
    like_count = Column(Integer, nullable=True)
    comment_count = Column(Integer, nullable=True)
    share_count = Column(Integer, nullable=True)
    # Bài viết Facebook cha mà đây là 1 COMMENT của nó — NULL nghĩa là bản ghi độc lập (bài viết gốc,
    # hoặc review/post của mọi nguồn khác không có khái niệm cha/con). ondelete="CASCADE": xoá bài
    # viết thì xoá luôn toàn bộ comment con, tránh mồ côi tham chiếu tới 1 post đã biến mất.
    parent_post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=True, index=True)
    # Link trực tiếp tới bài viết/comment gốc trên nền tảng nguồn — hiện chỉ Facebook điền (xem
    # src/pipeline/collectors/facebook.py), NULL với Google Play/App Store (không có permalink từng
    # review riêng, chỉ có trang app — xem _build_app_url trong routes_dashboard.py).
    source_url = Column(Text, nullable=True)
    # Điểm ưu tiên PHÂN TÍCH — heuristic thuần (từ khoá tiêu cực, tín hiệu có claim, rating thấp),
    # tính lúc thu thập (xem estimate_priority trong src/pipeline/processing/priority.py). Dùng để
    # sắp thứ tự hàng đợi khi quota LLM có hạn (run_analysis_cycle). Cố ý KHÔNG phải sentiment/kết
    # luận AI — Classification Agent mới là nơi quyết định sentiment thật.
    priority_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    topic = relationship("Topic", back_populates="posts")
    source = relationship("Source", back_populates="posts")
    prediction = relationship("Prediction", back_populates="post", uselist=False, cascade="all, delete-orphan")
    pain_point_links = relationship("PainPointPost", back_populates="post", cascade="all, delete-orphan")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Classification Agent
    sentiment = Column(Enum("positive", "neutral", "negative", name="sentiment_type"), nullable=True)
    topic_label = Column(String(50), nullable=True)
    severity_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    model_version = Column(String(50), nullable=True)
    classified_at = Column(DateTime(timezone=True), nullable=True)
    # True nếu nội dung CHỦ YẾU là câu hỏi/thắc mắc của khách (vd "app này có thu phí gì không?"),
    # KHÔNG phải nhận xét/phàn nàn. Cờ ĐỘC LẬP với sentiment (1 câu hỏi vẫn có thể mang giọng điệu
    # tiêu cực/tích cực) — cố ý không gộp vào/thay thế sentiment để không phá vỡ mọi chỗ đang group
    # theo sentiment (dashboard tổng, breakdown...). NULL = chưa phân tích.
    is_question = Column(Boolean, nullable=True)

    # Verification Agent — ĐỐI CHIẾU VĂN BẢN chính thức (QĐ 2345, TT 17/18, thông báo ngân hàng).
    # Đây KHÔNG phải xác minh danh tính khách hàng; xem verification_status bên dưới.
    reference_status = Column(Enum("matched", "no_match", "conflicting", name="reference_status_type"), nullable=True)
    reference_sources = Column(JSONB, nullable=False, default=list)
    reference_confidence = Column(Float, nullable=True)
    reference_checked_at = Column(DateTime(timezone=True), nullable=True)

    # XÁC MINH DANH TÍNH khách hàng — chỉ 'verified' khi đối chiếu được với CRM/hệ thống nội bộ.
    # Chưa có tích hợp CRM nên hiện luôn là 'unverified'. Cố ý KHÔNG tham gia vào việc ra kết luận
    # (consensus_status) — đây là thông tin ngữ cảnh cho người đọc, không phải đầu vào suy luận.
    verification_status = Column(
        Enum("verified", "unverified", name="identity_status_type"), nullable=False, default="unverified"
    )
    identity_checked_at = Column(DateTime(timezone=True), nullable=True)

    # AI đánh giá độ tin cậy NỘI DUNG dựa trên tính cụ thể của mô tả (do Classification Agent sinh
    # ra cùng lượt gọi LLM để không tốn thêm quota).
    content_reliability = Column(Enum("high", "medium", "low", name="content_reliability_type"), nullable=True)

    # Consensus Agent
    consensus_status = Column(
        Enum("confirmed", "needs_review", "dismissed", name="consensus_status_type"), nullable=True
    )
    final_confidence = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    consensus_at = Column(DateTime(timezone=True), nullable=True)
    # Cross-Check Agent — CHỈ chạy khi consensus_status ban đầu là "needs_review" (xem
    # graph.py::_should_cross_check), dùng model KHÁC HẲN kiến trúc (OpenAI, không phải chuỗi
    # Gemini/Gemma chính) để phân loại độc lập lần 2, xem src/analysis/cross_check.py. NULL = chưa
    # từng cross-check (case đủ rõ ràng ngay từ đầu, hoặc OPENAI_API_KEY chưa cấu hình). True/False
    # = đã cross-check, model độc lập thứ 2 có đồng thuận với phân loại gốc hay không — có thể đã
    # nâng consensus_status lên "confirmed" (đồng thuận) hoặc giữ "needs_review" kèm lý do rõ hơn
    # (bất đồng) — xem apply_cross_check() trong src/analysis/consensus.py.
    cross_check_agreed = Column(Boolean, nullable=True)

    # Seeding Agent — phát hiện review/bình luận GIẢ MẠO, DÀN DỰNG (khác is_spam ở Post: câu chữ rác
    # dễ nhận ra bằng heuristic; seeding thường viết tự nhiên, chỉ lộ khi xét cả giọng văn LẪN việc
    # đăng dồn dập cùng lúc với nhiều bài tương tự — xem src/analysis/graph.py::detect_seeding_node,
    # src/pipeline/processing/seeding.py::find_similar_recent_posts). CHỈ gắn cờ cảnh báo, KHÔNG tự
    # loại khỏi tính pain point (khác is_spam/is_duplicate) — để con người tự quyết, tránh sót bài
    # thật bị chấm nhầm. NULL/False = chưa phát hiện hoặc không nghi ngờ.
    is_seeding = Column(Boolean, nullable=False, default=False)
    seeding_reasoning = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    post = relationship("Post", back_populates="prediction")


class PainPoint(Base):
    __tablename__ = "pain_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    post_count = Column(Integer, nullable=False, default=0)
    trend = Column(Enum("increasing", "stable", "decreasing", name="trend_type"), nullable=True)
    sources = Column(JSONB, nullable=False, default=list)
    severity_avg = Column(Float, nullable=True)
    confidence_avg = Column(Float, nullable=True)
    # Kết quả gộp đối chiếu văn bản của các post thành viên (KHÔNG phải trạng thái xử lý —
    # vòng đời xử lý nằm ở lifecycle_status).
    reference_status = Column(
        Enum("matched", "no_match", "conflicting", name="painpoint_reference_status"),
        nullable=False,
        default="no_match",
    )
    last_notified_post_count = Column(Integer, nullable=True)
    # Doanh nghiệp TỰ đánh dấu pain point này là cấp thiết nhất với họ — ghi đè thứ hạng mặc định
    # theo severity_avg (xem list_pain_points/_pain_point_to_summary trong routes_dashboard.py).
    # Cho phép đánh dấu NHIỀU pain point (không giới hạn đúng 1), vẫn luôn đứng đầu danh sách so với
    # pain point chưa đánh dấu, sắp theo severity_avg NẾU có từ 2 pain point được đánh dấu trở lên.
    is_priority = Column(Boolean, nullable=False, default=False)

    # --- Vòng đời xử lý (con người vận hành), tách hẳn khỏi reference_status ở trên (máy đánh giá) ---
    lifecycle_status = Column(
        Enum("new", "in_progress", "resolved", "duplicate", "ignored", name="lifecycle_status_type"),
        nullable=False,
        default="new",
    )
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Text thay vì Enum: thêm/đổi tên phòng ban là chuyện thường xuyên của ngân hàng, không đáng
    # phải chạy migration mỗi lần. Danh sách gợi ý nằm ở frontend.
    department = Column(String(100), nullable=True)
    # hạn SLA — mặc định tính từ severity (xem src/sla.py), có thể bị quản lý ghi đè thủ công qua
    # due_at_overridden bên dưới.
    due_at = Column(DateTime(timezone=True), nullable=True)
    # True nếu quản lý đã tự đặt hạn — auto-recompute mỗi chu kỳ phân tích sẽ bỏ qua case này, xem
    # _upsert_pain_point trong src/analysis/pain_point.py.
    due_at_overridden = Column(Boolean, nullable=False, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    duplicate_of_id = Column(UUID(as_uuid=True), ForeignKey("pain_points.id", ondelete="SET NULL"), nullable=True)
    lifecycle_note = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    topic = relationship("Topic", back_populates="pain_points")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])
    duplicate_of = relationship("PainPoint", remote_side=[id], foreign_keys=[duplicate_of_id])
    post_links = relationship("PainPointPost", back_populates="pain_point", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="pain_point", cascade="all, delete-orphan")
    events = relationship(
        "PainPointEvent",
        back_populates="pain_point",
        cascade="all, delete-orphan",
        order_by="PainPointEvent.created_at",
    )


class PainPointEvent(Base):
    """Nhật ký thao tác xử lý — ai đổi trạng thái gì, lúc nào. Cần để truy vết "lỗi đã được khắc
    phục chưa" và để không mất lịch sử khi trạng thái bị đổi qua lại."""

    __tablename__ = "pain_point_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    pain_point_id = Column(
        UUID(as_uuid=True), ForeignKey("pain_points.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SET NULL: xoá tài khoản không được làm mất lịch sử xử lý đã diễn ra.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    pain_point = relationship("PainPoint", back_populates="events")
    user = relationship("User")


class PainPointPost(Base):
    """Bảng trung gian N-N giữa PainPoints và Posts."""

    __tablename__ = "pain_point_posts"

    pain_point_id = Column(UUID(as_uuid=True), ForeignKey("pain_points.id", ondelete="CASCADE"), primary_key=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    is_sample = Column(Boolean, nullable=False, default=False)

    pain_point = relationship("PainPoint", back_populates="post_links")
    post = relationship("Post", back_populates="pain_point_links")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # NULL cho contact_request — thông báo cấp NỀN TẢNG gửi tới platform admin khi có doanh nghiệp
    # gửi form "Liên hệ tư vấn" (xem routes_contact.py), không gắn với topic nào (doanh nghiệp CHƯA
    # có tài khoản/chủ đề lúc gửi form). Mọi notification_type khác vẫn LUÔN có topic_id.
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=True, index=True)
    # NULL cho daily_digest/contact_request — thông báo ở cấp topic/nền tảng, không gắn 1 pain point cụ thể.
    pain_point_id = Column(
        UUID(as_uuid=True), ForeignKey("pain_points.id", ondelete="CASCADE"), nullable=True, index=True
    )
    channel = Column(Enum("email", "web", "both", name="notification_channel"), nullable=False)
    # threshold_alert: pain point vượt ngưỡng cảnh báo của topic (check_and_notify). assigned/
    # resolved: gắn với vòng đời xử lý (xem src/notifications/service.py) — nhắm vào người phụ
    # trách (assigned_user_id), không phải chủ sở hữu topic. daily_digest: tổng hợp cấp topic, xem
    # src/notifications/digest.py. department_assigned: hệ thống TỰ gán phòng ban cho pain point
    # (xem src/analysis/department_routing.py) — gửi tới TOÀN BỘ nhân viên phòng ban đó (không phải
    # 1 assigned_user_id cụ thể như "assigned"), ai xử lý trước tự nhận qua LifecyclePanel.
    # contact_request: có doanh nghiệp gửi form liên hệ mới (routes_contact.py) — gửi tới TOÀN BỘ
    # platform admin, topic_id=None (xem comment cột topic_id ở trên).
    notification_type = Column(
        Enum(
            "threshold_alert",
            "assigned",
            "resolved",
            "daily_digest",
            "department_assigned",
            "contact_request",
            name="notification_type",
        ),
        nullable=False,
        default="threshold_alert",
    )
    severity = Column(Float, nullable=True)
    message = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    read_status = Column(Enum("unread", "read", name="read_status_type"), nullable=False, default="unread")

    user = relationship("User", back_populates="notifications")
    topic = relationship("Topic", back_populates="notifications")
    pain_point = relationship("PainPoint", back_populates="notifications")


class Payment(Base):
    """Giao dịch nâng cấp dùng thử lên chính thức qua VNPay — xem src/billing/vnpay.py và
    src/api/routes_billing.py. txn_ref UNIQUE để tra cứu khi VNPay redirect/gọi IPN về, và để chống
    xử lý trùng nếu VNPay gọi lại IPN nhiều lần cho cùng 1 giao dịch."""

    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    txn_ref = Column(String(64), unique=True, nullable=False)
    amount_vnd = Column(Integer, nullable=False)
    # String thuần (không phải Postgres Enum) — cố ý để tránh phải chạy migration ALTER TYPE nếu
    # sau này cần thêm trạng thái mới (vd "refunded").
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="payments")


class LLMUsage(Base):
    """1 dòng / 1 lượt gọi LLM thật đã thành công (Classification/Verification/Consensus/Pain Point
    description/News Sentiment — xem src/analysis/llm.py::pop_usage_log) — dùng để admin xem mức
    tiêu thụ token + chi phí ƯỚC TÍNH theo từng tài khoản (xem src/analysis/pricing.py).

    user_id/topic_id lưu TRỰC TIẾP (denormalized, không chỉ suy ra qua join Topic.user_id) và
    ondelete="SET NULL" — xoá topic/user sau này KHÔNG được xoá mất lịch sử tiêu thụ đã ghi nhận,
    chỉ mất đường link để xem lại thuộc về ai (chấp nhận được, vì mục đích chính là quan sát TỔNG
    chi phí vận hành hệ thống theo thời gian, không phải audit trail pháp lý)."""

    __tablename__ = "llm_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    call_type = Column(
        Enum(
            "classification",
            "verification",
            "consensus",
            "pain_point_description",
            "news_sentiment",
            "cross_check",
            "seeding_detection",
            "department_routing",
            name="llm_call_type",
        ),
        nullable=False,
    )
    model = Column(String(100), nullable=False)
    # Nullable: không phải provider/lượt gọi nào cũng trả usage_metadata (xem extract trong
    # llm.py) — vắng số liệu vẫn ghi lại ĐÃ gọi (call_type/model/created_at), chỉ thiếu token.
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class ContactRequest(Base):
    """1 yêu cầu "Liên hệ tư vấn" gửi từ trang giới thiệu công khai (xem POST /contact trong
    routes_contact.py — thay cho luồng tự đăng ký đã gỡ). Lưu lại để platform admin xem/xử lý qua
    GET /admin/contacts (trang /admin/contacts), KHÔNG chỉ dựa vào email — email có thể bị bỏ lỡ/
    rơi vào spam, lúc đó thông tin liên hệ sẽ mất hẳn nếu không lưu DB.

    Không gắn user_id nào — người gửi CHƯA có tài khoản trên hệ thống (đó chính là lý do họ liên hệ)."""

    __tablename__ = "contact_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    company_name = Column(String(255), nullable=False)
    contact_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(30), nullable=True)
    message = Column(Text, nullable=True)
    # Admin tự đánh dấu đã liên hệ lại/xử lý xong — KHÔNG có vòng đời nhiều trạng thái như PainPoint
    # (chỉ cần phân biệt "còn cần xem" và "đã xử lý", không cần department/SLA cho 1 lượt liên hệ).
    is_handled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
