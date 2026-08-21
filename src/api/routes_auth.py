import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
    VerifyEmailRequest,
)
from src.auth.security import create_access_token, hash_password, verify_password
from src.config import get_settings
from src.db.models import LLMUsage, OfficialDocument, Post, Prediction, Topic, User
from src.db.session import get_db
from src.logging_config import VN_TZ
from src.notifications.email import render_email, send_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

RESET_TOKEN_EXPIRE_MINUTES = 30
# Link xác thực email sống lâu hơn link đặt lại mật khẩu nhiều — đặt lại mật khẩu là hành động
# nhạy cảm cần làm ngay, còn xác thực email chỉ là "bấm khi nào rảnh", ép 30 phút sẽ khiến nhiều
# người bỏ lỡ.
VERIFICATION_TOKEN_EXPIRE_MINUTES = 24 * 60


def _find_user_by_identifier(identifier: str, db: Session) -> User | None:
    """Email hoặc username, không phân biệt hoa thường ở username (xem normalize_username)."""
    identifier = identifier.strip()
    return db.query(User).filter((User.email == identifier) | (User.username == identifier.lower())).first()


def _build_user_response(user: User, db: Session) -> UserResponse:
    """UserResponse dựng TAY (không dựa vào from_attributes trên object User) vì trial_daily_call_*/
    trial_daily_responses_analyzed/trial_expired không phải cột thật trên User — cần tính riêng qua
    query. Chỉ tính (tốn thêm query) khi đúng tài khoản dùng thử (is_paid=False + có trial_ends_at)
    — tài khoản trả phí/admin không cần, luôn trả None/False cho các field này.

    trial_daily_call_count đếm LƯỢT GỌI LLM (dùng để so với trial_daily_call_limit — cơ chế thật sự
    tạm dừng phân tích, xem _trial_users_blocked_from_analysis trong src/analysis/runner.py) — CHỈ
    dùng để kiểm tra hết trần chưa, KHÔNG dùng để hiển thị cho người dùng vì 1 phản hồi tốn 2-3 lượt
    gọi (classify+verify+consensus), hiển thị thẳng số này ra sẽ khiến người dùng hiểu nhầm là số
    phản hồi (từng xảy ra: banner cũ ghi "50 lượt phân tích AI" khiến người dùng tưởng 50 phản hồi,
    trong khi thực tế chỉ ~17-25 phản hồi). trial_daily_responses_analyzed đếm ĐÚNG số phản hồi thật
    đã có Prediction hôm nay (COUNT Prediction, không phải COUNT llm_usage) — đây mới là số hiển thị
    cho người dùng, khớp đúng dữ liệu phân tích thật, không suy diễn theo tỷ lệ ước tính.

    trial_expired: True khi đã hết hạn THỜI GIAN (trial_ends_at) HOẶC hết trần TRỌN ĐỜI
    (trial_analysis_call_limit) — KHÔNG khoá đăng nhập (khác trước đây), chỉ để frontend hiện banner
    mời nâng cấp (xem TrialQuotaBanner.tsx) vì _trial_users_blocked_from_analysis đã tạm dừng phân
    tích thêm cho tài khoản này ở phía backend rồi."""
    daily_limit: int | None = None
    daily_count: int | None = None
    daily_responses_analyzed: int | None = None
    daily_crawl_limit: int | None = None
    daily_crawl_count: int | None = None
    trial_expired = False
    if not user.is_paid and user.trial_ends_at is not None:
        trial_expired_by_time = user.trial_ends_at < datetime.now(UTC)
        lifetime_call_count = db.query(func.count(LLMUsage.id)).filter(LLMUsage.user_id == user.id).scalar() or 0
        trial_expired_by_usage = lifetime_call_count >= get_settings().trial_analysis_call_limit
        trial_expired = trial_expired_by_time or trial_expired_by_usage

        daily_limit = get_settings().trial_daily_call_limit
        # Giờ VN (không phải UTC) — đồng bộ mốc reset với _trial_users_blocked_from_analysis
        # (src/analysis/runner.py) và _trial_daily_crawl_remaining (src/pipeline/runner.py); cả 3
        # nơi PHẢI cùng 1 mốc, lệch nhau sẽ khiến số hiển thị ở đây không khớp lúc nào thật sự bị
        # chặn phân tích/thu thập.
        today_start = datetime.now(VN_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        daily_count = (
            db.query(func.count(LLMUsage.id))
            .filter(LLMUsage.user_id == user.id, LLMUsage.created_at >= today_start)
            .scalar()
            or 0
        )
        daily_responses_analyzed = (
            db.query(func.count(Prediction.id))
            .join(Post, Post.id == Prediction.post_id)
            .join(Topic, Topic.id == Post.topic_id)
            .filter(Topic.user_id == user.id, Prediction.classified_at >= today_start)
            .scalar()
            or 0
        )
        # Đếm giống hệt _trial_daily_crawl_remaining trong src/pipeline/runner.py (nơi trần này
        # THẬT SỰ chặn thu thập) — gộp Post + OfficialDocument mới thu thập hôm nay của MỌI topic
        # user này sở hữu.
        daily_crawl_limit = get_settings().trial_daily_crawl_limit
        posts_today = (
            db.query(func.count(Post.id))
            .join(Topic, Topic.id == Post.topic_id)
            .filter(Topic.user_id == user.id, Post.collected_at >= today_start)
            .scalar()
            or 0
        )
        docs_today = (
            db.query(func.count(OfficialDocument.id))
            .join(Topic, Topic.id == OfficialDocument.topic_id)
            .filter(Topic.user_id == user.id, OfficialDocument.first_seen_at >= today_start)
            .scalar()
            or 0
        )
        daily_crawl_count = posts_today + docs_today
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_verified=user.is_verified,
        is_platform_admin=user.is_platform_admin,
        is_paid=user.is_paid,
        trial_ends_at=user.trial_ends_at,
        created_at=user.created_at,
        trial_expired=trial_expired,
        trial_daily_call_limit=daily_limit,
        trial_daily_call_count=daily_count,
        trial_daily_responses_analyzed=daily_responses_analyzed,
        trial_daily_crawl_limit=daily_crawl_limit,
        trial_daily_crawl_count=daily_crawl_count,
    )


def _send_verification_email(user: User, db: Session) -> None:
    user.verification_token = secrets.token_urlsafe(32)
    user.verification_token_expires_at = datetime.now(UTC) + timedelta(minutes=VERIFICATION_TOKEN_EXPIRE_MINUTES)
    db.commit()

    verify_link = f"{get_settings().frontend_base_url}/verify-email?token={user.verification_token}"
    send_email(
        to=user.email,
        subject="Xác thực tài khoản",
        html_body=render_email(
            heading="Xác thực tài khoản của bạn",
            body_html=f"<p>Nhấn nút bên dưới để xác thực tài khoản (hết hạn sau {VERIFICATION_TOKEN_EXPIRE_MINUTES // 60} giờ).</p>",
            cta_url=verify_link,
            cta_label="Xác thực tài khoản",
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = _find_user_by_identifier(payload.identifier, db)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Email/tên đăng nhập hoặc mật khẩu không đúng"
        )
    # Kiểm tra sau khi đã xác nhận mật khẩu đúng — không để kẻ đoán mật khẩu phân biệt được
    # "sai mật khẩu" với "đúng mật khẩu nhưng chưa xác thực" qua thông báo lỗi khác nhau.
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản chưa được xác thực. Vui lòng kiểm tra email hoặc gửi lại email xác thực.",
        )
    # Hết hạn dùng thử (thời gian HOẶC trần trọn đời) KHÔNG khoá đăng nhập — chỉ tạm dừng phân tích
    # thêm (xem _trial_users_blocked_from_analysis trong src/analysis/runner.py) và hiện banner mời
    # nâng cấp trong dashboard (UserResponse.trial_expired, xem _build_user_response ngay dưới đây).
    # Trước đây chặn hẳn ở đây (402, không cấp token) — người dùng bị đá ra khỏi dashboard ngay khi
    # hết hạn dù dữ liệu/pain point cũ vẫn còn nguyên giá trị tham khảo, chỉ là không phân tích thêm
    # được nữa; giờ vẫn vào xem bình thường, chỉ thiếu dữ liệu MỚI.
    return TokenResponse(access_token=create_access_token(subject=str(user.id)))


@router.post("/verify-email", response_model=TokenResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.verification_token == payload.token).first()
    if (
        user is None
        or user.verification_token_expires_at is None
        or user.verification_token_expires_at < datetime.now(UTC)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token không hợp lệ hoặc đã hết hạn")

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires_at = None
    db.commit()

    # Đăng nhập luôn sau khi xác thực — tránh bắt người dùng vừa bấm link xong lại phải gõ mật
    # khẩu thêm 1 lần nữa.
    return TokenResponse(access_token=create_access_token(subject=str(user.id)))


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)) -> None:
    user = _find_user_by_identifier(payload.identifier, db)
    # Im lặng bỏ qua khi không tìm thấy hoặc đã xác thực rồi — không tiết lộ tài khoản có tồn tại
    # hay không, cùng nguyên tắc với forgot-password.
    if user is None or user.is_verified:
        return None

    _send_verification_email(user, db)
    return None


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserResponse:
    return _build_user_response(current_user, db)


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    db.commit()
    db.refresh(current_user)
    return _build_user_response(current_user, db)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Mật khẩu hiện tại không đúng")
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> None:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        # Không tiết lộ email có tồn tại trong hệ thống hay không.
        return None

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires_at = datetime.now(UTC) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    db.commit()

    reset_link = f"{get_settings().frontend_base_url}/reset-password?token={token}"
    send_email(
        to=user.email,
        subject="Đặt lại mật khẩu",
        html_body=render_email(
            heading="Đặt lại mật khẩu",
            body_html=f"<p>Nhấn nút bên dưới để đặt lại mật khẩu (hết hạn sau {RESET_TOKEN_EXPIRE_MINUTES} phút).</p>",
            cta_url=reset_link,
            cta_label="Đặt lại mật khẩu",
        ),
    )
    return None


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    user = db.query(User).filter(User.reset_token == payload.token).first()
    if user is None or user.reset_token_expires_at is None or user.reset_token_expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token không hợp lệ hoặc đã hết hạn")

    user.password_hash = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    db.commit()
