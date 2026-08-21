from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field

# bcrypt có giới hạn cứng 72 byte cho mật khẩu — chặn ở tầng schema để báo lỗi rõ ràng thay vì
# im lặng cắt bớt mật khẩu.
_PASSWORD_MAX_LENGTH = 72


class LoginRequest(BaseModel):
    # Nhận cả "identifier", "email" hay "username" làm tên trường trong request — giữ tương thích
    # với client cũ vốn gửi {"email": ...}, đồng thời cho phép đăng nhập bằng tên đăng nhập.
    identifier: str = Field(validation_alias=AliasChoices("identifier", "email", "username"))
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # str chứ không phải EmailStr: đây là output echo lại giá trị đã lưu (đã validate lúc ghi, hoặc
    # do admin tạo hộ qua POST /topics/admin), không phải input mới cần validate định dạng. Dùng
    # EmailStr ở đây từng khiến GET /auth/me trả 500 (ResponseValidationError) với bất kỳ email nào
    # có TLD bị email-validator coi là special-use/reserved (vd .local) — lỗi không liên quan gì
    # đến CORS dù trình duyệt hiển thị y hệt lỗi CORS (CORSMiddleware không gắn được header vào
    # response khi app phía trong ném exception chưa bắt).
    email: str
    username: str | None
    full_name: str | None
    is_verified: bool
    is_platform_admin: bool
    is_paid: bool
    trial_ends_at: datetime | None
    created_at: datetime
    # True khi đã hết hạn THỜI GIAN (trial_ends_at) HOẶC hết trần TRỌN ĐỜI (trial_analysis_call_limit
    # trong src/config.py) — KHÔNG khoá đăng nhập/dashboard, chỉ để frontend hiện banner mời nâng
    # cấp THƯỜNG TRỰC (xem TrialQuotaBanner.tsx). Backend đã tự tạm dừng phân tích thêm cho tài
    # khoản này (xem _trial_users_blocked_from_analysis trong src/analysis/runner.py) — banner này
    # chỉ là THÔNG BÁO, không phải cơ chế chặn. Luôn False với tài khoản không phải dùng thử.
    trial_expired: bool = False
    # None nếu KHÔNG phải tài khoản dùng thử (is_paid=True hoặc trial_ends_at=None) — chỉ tài khoản
    # dùng thử mới bị áp trần phân tích MIỄN PHÍ TRONG NGÀY (UTC, xem trial_daily_call_limit trong
    # src/config.py), TÁCH BIỆT với trần TRỌN ĐỜI ở trial_expired phía trên (đó tạm dừng VĨNH VIỄN
    # tới khi nâng cấp, còn trần ngày chỉ tạm dừng tới ngày mai) — cả 2 đều không khoá đăng nhập, chỉ
    # để frontend hiện banner "đã dùng hết lượt phân tích miễn phí hôm nay, mai quay lại hoặc nâng
    # cấp" — xem _build_user_response() trong routes_auth.py và _trial_users_blocked_from_analysis()
    # trong src/analysis/runner.py (nơi trần này THẬT SỰ tạm dừng phân tích thêm cho tài khoản đó).
    trial_daily_call_limit: int | None = None
    trial_daily_call_count: int | None = None
    # Số PHẢN HỒI thật đã có Prediction hôm nay (COUNT Prediction, KHÁC trial_daily_call_count đếm
    # lượt gọi LLM thô) — dùng để hiển thị cho người dùng, vì 1 phản hồi tốn 2-3 lượt gọi
    # (classify+verify+consensus) nên trial_daily_call_count KHÔNG phản ánh đúng số phản hồi thật,
    # dễ gây hiểu nhầm nếu hiển thị thẳng (xem TrialQuotaBanner.tsx).
    trial_daily_responses_analyzed: int | None = None
    # Trần THU THẬP (Collector Agent) MIỄN PHÍ TRONG NGÀY — TÁCH BIỆT với 3 field phân tích AI ở
    # trên (xem trial_daily_crawl_limit trong src/config.py, _trial_daily_crawl_remaining trong
    # src/pipeline/runner.py — nơi trần này THẬT SỰ chặn bớt số bản ghi crawl mỗi nguồn). None nếu
    # KHÔNG phải tài khoản dùng thử.
    trial_daily_crawl_limit: int | None = None
    trial_daily_crawl_count: int | None = None


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=_PASSWORD_MAX_LENGTH)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=_PASSWORD_MAX_LENGTH)


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    # Cùng kiểu identifier (email hoặc username) như LoginRequest — người bị chặn đăng nhập vì
    # chưa xác thực có thể đã gõ username, không nhớ chính xác email đã đăng ký.
    identifier: str = Field(validation_alias=AliasChoices("identifier", "email", "username"))
