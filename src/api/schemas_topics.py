from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

SourceType = Literal["google_play", "app_store", "linkedin", "bank_website", "facebook", "news_article", "tiktok"]
TopicStatus = Literal["active", "archived"]
NotifyChannel = Literal["email", "web", "both"]
DocumentCategory = Literal["notice", "policy", "fee", "incident", "maintenance", "product", "other"]


class SourceCreate(BaseModel):
    type: SourceType
    config: dict = Field(default_factory=dict)
    # Lịch crawl riêng cho nguồn này (phút) — None (mặc định) nghĩa là dùng nhịp scheduler chung
    # (collection_interval_minutes), giống hành vi cũ. Hữu ích cho nguồn ít thay đổi (vd
    # bank_website) để không crawl lại mỗi 15-30 phút như review.
    crawl_interval_minutes: int | None = Field(default=None, ge=1)
    # Trọng số ưu tiên PHÂN TÍCH (không phải crawl) — mặc định 1 = ngang hàng mọi nguồn khác (round
    # robin đều, xem rank_within_source trong src/analysis/runner.py). Doanh nghiệp tự đặt số lớn
    # hơn cho nguồn cần phân tích gấp/thường xuyên hơn.
    analysis_priority: int = Field(default=1, ge=1)


class SourceUpdate(BaseModel):
    config: dict | None = None
    is_active: bool | None = None
    crawl_interval_minutes: int | None = None
    analysis_priority: int | None = Field(default=None, ge=1)


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    config: dict
    is_active: bool
    crawl_interval_minutes: int | None = None
    last_crawled_at: datetime | None = None
    analysis_priority: int = 1


class OfficialDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    title: str
    url: str
    content: str | None
    published_at: datetime | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    # Sắc thái đưa tin (News Sentiment Agent) — chỉ có với category="news", None với mọi category
    # khác (xem src/db/models.py::OfficialDocument).
    sentiment: str | None = None
    sentiment_classified_at: datetime | None = None


class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    keywords: list[str] = Field(default_factory=list)
    alert_threshold: int = Field(default=10, ge=1)
    notify_enabled: bool = True
    notify_channel: NotifyChannel = "both"
    # Tự động gán PHÒNG BAN cho pain point mới (xem src/analysis/department_routing.py) — mặc định
    # TẮT (opt-in), khác notify_enabled mặc định bật, vì đây là hành vi tự động ghi dữ liệu xử lý
    # việc, cần chủ đề chủ động bật.
    auto_assign_enabled: bool = False
    sources: list[SourceCreate] = Field(default_factory=list)


class AdminTopicCreate(TopicCreate):
    """Dùng cho POST /topics/admin — admin tạo topic THAY doanh nghiệp khác, kèm tạo (hoặc dùng
    lại nếu email đã có sẵn) tài khoản chủ sở hữu cho họ. Không nhận mật khẩu từ admin — tài khoản
    MỚI được tạo với mật khẩu ngẫu nhiên không ai biết, chủ sở hữu tự đặt mật khẩu qua link gửi
    trong email (xem admin_create_topic trong routes_topics.py)."""

    owner_email: EmailStr
    owner_full_name: str | None = Field(default=None, max_length=255)
    # Chỉ áp dụng khi owner_email CHƯA có tài khoản — bỏ qua nếu dùng lại user đã tồn tại (không
    # đụng trạng thái thanh toán hiện có của họ). "trial": có hạn dùng thử (settings.trial_duration_days
    # ngày), hết hạn thì bị khoá đăng nhập cho tới khi nâng cấp qua VNPay. "paid": không giới hạn
    # ngay từ đầu — dùng khi doanh nghiệp đã thanh toán qua kênh khác (vd chuyển khoản ngoài hệ
    # thống) trước khi admin tạo tài khoản.
    plan: Literal["trial", "paid"] = "trial"


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    keywords: list[str] | None = None
    alert_threshold: int | None = Field(default=None, ge=1)
    notify_enabled: bool | None = None
    notify_channel: NotifyChannel | None = None
    status: TopicStatus | None = None
    auto_assign_enabled: bool | None = None


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    keywords: list
    alert_threshold: int
    notify_enabled: bool
    notify_channel: str
    status: str
    created_at: datetime
    sources: list[SourceResponse] = Field(default_factory=list)
    # Người đang gọi có phải chủ sở hữu không — để frontend biết có hiện nút quản trị (sửa chủ đề,
    # mời/xoá thành viên) hay không. Trả cờ này thay vì user_id để không lộ id của người khác.
    is_owner: bool = False
    auto_assign_enabled: bool = False


class TopicMemberCreate(BaseModel):
    """Thêm nhân viên vào chủ đề bằng email. Nếu email đã có tài khoản (vd đang làm ở chủ đề khác)
    thì thêm thẳng làm thành viên; chưa có thì hệ thống TỰ TẠO tài khoản mới (xem add_member() trong
    routes_topics.py) — không còn yêu cầu người được thêm phải tự đăng ký trước."""

    email: EmailStr
    # Phòng ban của nhân viên này TRONG chủ đề này — nguồn để tự động phân việc (xem
    # src/analysis/department_routing.py) khi Topic.auto_assign_enabled bật. Free text, không bắt
    # buộc (chủ đề không dùng auto-assign không cần điền).
    department: str | None = Field(default=None, max_length=100)


class TopicMemberUpdate(BaseModel):
    """Sửa phòng ban của 1 nhân viên đã có trong chủ đề — trước đây chỉ có thêm/xoá thành viên,
    không sửa được gì sau khi thêm."""

    department: str | None = Field(default=None, max_length=100)
