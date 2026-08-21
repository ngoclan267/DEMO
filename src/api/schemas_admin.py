from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminUserUsageSummary(BaseModel):
    """Tổng token đã dùng + chi phí ƯỚC TÍNH (xem src/analysis/pricing.py) — gộp từ mọi topic của
    tài khoản này, không tách theo topic (xem topics[].usage trong AdminUserDetail để tách theo topic)."""

    total_input_tokens: int
    total_output_tokens: int
    call_count: int
    # Luôn là số cụ thể (0.0 nếu chưa dùng gì) — CHỈ cộng phần model ĐÃ xác định được giá. Xem
    # has_unpriced_usage để biết số này có phải TOÀN BỘ chi phí hay chỉ 1 phần (còn model chưa rõ giá).
    estimated_cost_usd: float
    has_unpriced_usage: bool


class AdminUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    username: str | None
    is_platform_admin: bool
    is_paid: bool
    is_verified: bool
    trial_ends_at: datetime | None
    created_at: datetime
    topic_count: int
    usage: AdminUserUsageSummary
    # None nếu KHÔNG phải tài khoản dùng thử (is_paid=True hoặc trial_ends_at=None, xem
    # User.is_paid) — chỉ tài khoản dùng thử mới bị áp trần lượt gọi AI miễn phí này (xem
    # trial_analysis_call_limit trong src/config.py, routes_auth.py::login). So với
    # usage.call_count để biết còn bao nhiêu lượt trước khi bị khoá đăng nhập.
    trial_analysis_call_limit: int | None


class AdminTopicSummary(BaseModel):
    id: UUID
    name: str
    status: str
    created_at: datetime
    source_count: int
    post_count: int
    pain_point_count: int
    usage: AdminUserUsageSummary


class AdminUserDetail(AdminUserSummary):
    topics: list[AdminTopicSummary] = Field(default_factory=list)


class AdminUserUpdate(BaseModel):
    """Tri-state qua exclude_unset (giống LifecycleUpdateRequest) — chỉ field THỰC SỰ gửi lên mới
    bị đổi, tránh 1 field vắng mặt bị hiểu nhầm thành "đặt về None/False"."""

    full_name: str | None = None
    is_paid: bool | None = None
    is_platform_admin: bool | None = None
    # None = không giới hạn (xem User.trial_ends_at) — vẫn cần phân biệt được với "không gửi field
    # này lên" (exclude_unset lo phần đó), nên cứ để Optional bình thường ở đây.
    trial_ends_at: datetime | None = None


class AdminContactSummary(BaseModel):
    """1 yêu cầu "Liên hệ tư vấn" (xem POST /contact, ContactRequest trong src/db/models.py)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_name: str
    contact_name: str
    email: str
    phone: str | None
    message: str | None
    is_handled: bool
    created_at: datetime


class AdminContactUpdate(BaseModel):
    is_handled: bool
