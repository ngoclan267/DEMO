from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.analysis.schemas import ReferenceSource


class TrendPoint(BaseModel):
    date: date
    count: int
    negative_count: int


class HourlyTrendPoint(BaseModel):
    """1 điểm trend theo GIỜ trong 1 ngày cụ thể — zoom chi tiết từ TrendPoint (theo ngày), dùng ở
    GET /pain-points/{id}/trend/hourly và GET /topics/{id}/trend/hourly. `hour` là mốc đầu giờ theo
    giờ Việt Nam (0h, 1h, ... 23h) của đúng ngày được yêu cầu qua query param `date`."""

    hour: datetime
    count: int
    negative_count: int


class PeriodTrendPoint(BaseModel):
    """1 điểm trend trong GET /topics/{id}/compare-periods — thêm positive_count so với TrendPoint
    dùng ở dashboard chính (get_dashboard), vì frontend (PeriodTrendChart.tsx) cho chọn xem đường
    Tất cả/Tiêu cực/Tích cực, còn TrendChart.tsx (dashboard chính) chỉ vẽ tổng số + tiêu cực nên
    không cần positive_count — tách schema riêng thay vì thêm field không dùng vào TrendPoint."""

    date: date
    count: int
    negative_count: int
    positive_count: int


class PeriodStats(BaseModel):
    """Số liệu của 1 mốc thời gian trong GET /topics/{id}/compare-periods — thay cho so sánh
    topic-với-topic cũ (không còn hợp lý khi mỗi ngân hàng là 1 workspace riêng biệt), giờ so sánh
    2 giai đoạn trong CÙNG 1 topic."""

    date_from: date
    date_to: date
    post_count: int
    sentiment_breakdown: dict[str, int]
    # Cùng định nghĩa/nguồn dữ liệu với DashboardSummary.negative_by_group bên dưới, chỉ giới hạn
    # trong khoảng [date_from, date_to] thay vì toàn bộ lịch sử.
    negative_by_group: dict[str, int]
    # Pain point MỚI PHÁT SINH trong giai đoạn (PainPoint.created_at rơi trong khoảng) — không phải
    # tổng số pain point đang mở tính đến thời điểm đó.
    pain_point_count: int
    # Số liệu THEO NGÀY trong giai đoạn — vẽ biểu đồ đường so 2 giai đoạn cạnh nhau ở frontend
    # (PeriodTrendChart.tsx, cho chọn xem Tất cả/Tiêu cực/Tích cực), CÙNG định nghĩa/nguồn dữ liệu
    # với DashboardSummary.trend (chỉ post ĐÃ phân tích, xem get_dashboard). date của mỗi điểm là
    # ngày dương lịch thật trong giai đoạn — frontend tự quy về "ngày thứ N kể từ đầu giai đoạn" để
    # so hình dạng 2 đường bất kể lệch ngày lịch (vd giai đoạn A tháng trước, giai đoạn B tháng này).
    trend: list[PeriodTrendPoint]


class PeriodComparisonResponse(BaseModel):
    period_a: PeriodStats
    period_b: PeriodStats


class AssigneeRef(BaseModel):
    """Người phụ trách — chỉ lộ tên hiển thị và email trong phạm vi 1 chủ đề (người xem đã là
    thành viên chủ đề đó nên biết nhau)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    # Phòng ban của người này TRONG chủ đề đang xem (topic_members.department) — None cho chủ sở
    # hữu (không phải thành viên, không cần phòng ban) hoặc thành viên chưa được gán. Nguồn cho tự
    # động phân việc, xem src/analysis/department_routing.py.
    department: str | None = None


class PainPointSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    post_count: int
    trend: str | None
    reference_status: str
    severity_avg: float | None
    confidence_avg: float | None
    sources: list
    # Doanh nghiệp tự đánh dấu là cấp thiết nhất — luôn đứng đầu danh sách bất kể severity_avg (xem
    # PainPoint.is_priority trong src/db/models.py). False mặc định = sắp theo severity_avg như cũ.
    is_priority: bool

    # --- Vòng đời xử lý + SLA ---
    lifecycle_status: str
    assigned_user: AssigneeRef | None
    department: str | None
    due_at: datetime | None
    # True nếu quản lý đã tự đặt hạn (không phải tính tự động từ severity) — xem src/sla.py.
    due_at_overridden: bool
    resolved_at: datetime | None
    duplicate_of_id: UUID | None
    lifecycle_note: str | None
    # Tính sẵn ở server để mọi nơi hiển thị dùng chung một định nghĩa quá hạn (xem src/sla.py),
    # tránh mỗi màn hình tự so sánh ngày một kiểu.
    is_breached: bool
    severity_level: str


class LifecycleUpdateRequest(BaseModel):
    # Tri-state qua exclude_unset giống mọi field khác ở đây — vắng mặt = không đụng, có mặt = đặt
    # đúng giá trị gửi lên (kể cả đặt lại False để bỏ đánh dấu).
    is_priority: bool | None = None
    lifecycle_status: str | None = Field(default=None, pattern="^(new|in_progress|resolved|duplicate|ignored)$")
    assigned_user_id: UUID | None = None
    department: str | None = Field(default=None, max_length=100)
    duplicate_of_id: UUID | None = None
    note: str | None = None
    # Tri-state qua exclude_unset — KHÔNG suy luận từ due_at có mặt hay không (frontend gửi lại mọi
    # field mỗi lần lưu, kể cả lưu không liên quan): vắng mặt = không đụng due_at; True = đặt due_at
    # theo giá trị gửi kèm + đánh dấu overridden; False = xoá cờ, tính lại theo severity.
    due_at: datetime | None = None
    due_at_override: bool | None = None


class PainPointEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_status: str | None
    to_status: str | None
    note: str | None
    created_at: datetime
    user: AssigneeRef | None


class DashboardSummary(BaseModel):
    negative_posts_count: int
    total_posts_count: int
    analyzed_posts_count: int
    pending_analysis_count: int
    severity_breakdown: dict[str, int]
    source_breakdown: dict[str, int]
    # Số phản hồi theo cảm xúc (positive/neutral/negative) trên toàn bộ dữ liệu đã phân tích của
    # topic — để người dùng đánh giá tổng quan tình hình, không chỉ nhìn riêng pain point (vốn chỉ
    # là các nhóm ĐÃ vượt ngưỡng cảnh báo).
    sentiment_breakdown: dict[str, int]
    # Số phản hồi TIÊU CỰC theo từng nhóm chủ đề (topic_label — ưu tiên 1 trong các nhãn gợi ý ở
    # src/analysis/schemas.py::SUGGESTED_TOPIC_LABELS, nhưng KHÔNG còn là tập đóng, Classification
    # Agent có thể tự đặt nhãn mới), không giới hạn ở pain point đã vượt ngưỡng — cho biểu đồ so
    # sánh mức độ tiêu cực giữa các nhóm. Bỏ qua post chưa phân loại được nhóm (topic_label NULL,
    # hiếm gặp — xem Classification Agent).
    negative_by_group: dict[str, int]
    trend: list[TrendPoint]
    top_pain_points: list[PainPointSummary]
    # --- Theo dõi xử lý ---
    overdue_count: int
    due_soon_count: int
    lifecycle_breakdown: dict[str, int]


class SourceRef(BaseModel):
    source_type: str
    app_url: str | None


class PostSummary(BaseModel):
    """PII-safe: chỉ chứa nội dung đã làm sạch — KHÔNG BAO GIỜ chứa raw_content (có tên người
    đánh giá gốc từ Google Play/App Store)."""

    id: UUID
    content: str
    language: str
    sentiment: str | None
    topic_label: str | None
    severity_score: float | None
    is_spam: bool
    # Cảnh báo nghi ngờ review/bình luận GIẢ MẠO, DÀN DỰNG (Seeding Agent) — CHỈ cảnh báo, post này
    # vẫn được tính vào pain point bình thường (khác is_spam). None/False = chưa phân tích hoặc
    # không nghi ngờ. Xem src/db/models.py::Prediction.is_seeding.
    is_seeding: bool = False
    seeding_reasoning: str | None = None
    posted_at: datetime | None
    collected_at: datetime | None
    source_type: str | None
    # Trạng thái xử lý của pain point chứa post này (None nếu chưa thuộc pain point nào — nhóm
    # chủ đề chưa đủ ngưỡng cảnh báo). Khác consensus_status (đánh giá của AI) — đây là vòng đời
    # xử lý do con người vận hành, xem src/sla.py và PainPoint.lifecycle_status.
    pain_point_lifecycle_status: str | None = None
    # Điểm ưu tiên PHÂN TÍCH — heuristic thuần, KHÔNG phải sentiment (xem
    # src/pipeline/processing/priority.py). Hiển thị để minh bạch vì sao post này được/chưa được
    # phân tích trước trong hàng đợi khi quota LLM có hạn.
    priority_score: float = 0.0
    # Số liệu tương tác — hiện chỉ có với bài viết Facebook (xem
    # src/pipeline/collectors/facebook.py), None với mọi nguồn khác.
    like_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    # True/False = AI đã phân loại là câu hỏi/nhận xét; None = chưa phân tích. Xem
    # src/db/models.py::Prediction.is_question.
    is_question: bool | None = None
    # ID bài viết Facebook cha nếu đây là 1 COMMENT (xem Post.parent_post_id); None với bài viết gốc
    # và mọi nguồn khác không có khái niệm bài viết-comment.
    parent_post_id: UUID | None = None
    # Link trực tiếp tới bài viết/comment gốc trên nền tảng nguồn — hiện chỉ Facebook có, None với
    # nguồn khác (xem Post.source_url).
    source_url: str | None = None


class PostDetail(PostSummary):
    # 3 khái niệm tách bạch, cố ý KHÔNG gộp vào một chữ "xác minh" (xem src/db/models.py):
    verification_status: str | None  # xác minh DANH TÍNH khách hàng (CRM) — hiện luôn 'unverified'
    content_reliability: str | None  # AI đánh giá độ cụ thể của NỘI DUNG
    reference_status: str | None  # đối chiếu VĂN BẢN chính thức
    # Tài liệu cụ thể mà Verification Agent tìm được khớp (title/url/relation) — trước đây chỉ có
    # reference_status (tổng kết matched/no_match/conflicting) mà không cho xem ĐƯỢC tài liệu nào,
    # dù dữ liệu này đã lưu sẵn ở predictions.reference_sources từ trước. Rỗng khi reference_status
    # không phải 'matched'.
    reference_sources: list[ReferenceSource] = Field(default_factory=list)
    consensus_status: str | None  # kết luận của AI
    reasoning: str | None
    # None = chưa cross-check (case đủ rõ ràng ngay từ Consensus, không cần — xem
    # src/analysis/graph.py::_should_cross_check). True/False = đã cross-check bằng model độc lập
    # thứ 2 (xem src/analysis/cross_check.py), có đồng thuận với phân loại gốc hay không.
    cross_check_agreed: bool | None = None
    source: SourceRef | None
    # Phản hồi của nhà phát triển/ngân hàng — None nếu chưa có phản hồi hoặc nguồn không hỗ trợ
    # (hiện chỉ Google Play có, xem src/pipeline/collectors/google_play.py).
    reply_content: str | None
    reply_at: datetime | None
