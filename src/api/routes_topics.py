import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.deps import get_accessible_topic, get_owned_topic
from src.api.schemas_dashboard import AssigneeRef
from src.api.schemas_topics import (
    AdminTopicCreate,
    OfficialDocumentResponse,
    SourceCreate,
    SourceResponse,
    SourceUpdate,
    TopicMemberCreate,
    TopicMemberUpdate,
    TopicResponse,
    TopicUpdate,
)
from src.auth.dependencies import get_current_user, get_platform_admin
from src.auth.security import hash_password
from src.config import get_settings
from src.db.models import OfficialDocument, Source, Topic, TopicMember, User
from src.db.session import get_db
from src.notifications.email import render_email, send_email

router = APIRouter(prefix="/topics", tags=["topics"])

# Link đặt mật khẩu lần đầu sống lâu hơn link "quên mật khẩu" thường (30 phút, xem
# RESET_TOKEN_EXPIRE_MINUTES trong routes_auth.py) — đây không phải tình huống khẩn cấp, doanh
# nghiệp có thể không mở email ngay, ép hết hạn quá nhanh sẽ khiến nhiều người bỏ lỡ.
_WELCOME_TOKEN_EXPIRE_MINUTES = 24 * 60


def _to_response(topic: Topic, current_user: User) -> TopicResponse:
    """Gắn cờ is_owner theo người đang gọi — cùng một topic có thể là "của tôi" với người này và
    "được mời" với người kia."""
    return TopicResponse.model_validate(topic).model_copy(update={"is_owner": topic.user_id == current_user.id})


def _get_owned_source(topic: Topic, source_id: UUID, db: Session) -> Source:
    source = db.query(Source).filter(Source.id == source_id, Source.topic_id == topic.id).first()
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy source")
    return source


@router.get("", response_model=list[TopicResponse])
def list_topics(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TopicResponse]:
    """Chủ đề của chính mình VÀ chủ đề được mời làm thành viên."""
    topics = (
        db.query(Topic)
        .outerjoin(TopicMember, TopicMember.topic_id == Topic.id)
        .filter((Topic.user_id == current_user.id) | (TopicMember.user_id == current_user.id))
        .order_by(Topic.created_at.desc())
        .all()
    )
    return [_to_response(t, current_user) for t in topics]


@router.post("/admin", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
def admin_create_topic(
    payload: AdminTopicCreate,
    admin: User = Depends(get_platform_admin),
    db: Session = Depends(get_db),
) -> Topic:
    """Quản trị TỔNG nền tảng tạo topic THAY doanh nghiệp khác, kèm tạo (hoặc dùng lại nếu đã có
    sẵn) tài khoản chủ sở hữu cho họ. Sau khi tạo, topic chạy pipeline thu thập+phân tích bình
    thường như mọi topic khác — run_cycle/run_analysis_cycle tự quét mọi topic status=active,
    không cần xử lý riêng gì thêm ở đây."""
    settings = get_settings()
    owner = db.query(User).filter(User.email == payload.owner_email).first()
    is_new_owner = owner is None
    if owner is None:
        # Mật khẩu ngẫu nhiên không ai biết/gõ được — admin không tự đặt/biết mật khẩu thật của
        # doanh nghiệp, chủ sở hữu tự đặt qua link gửi trong email ngay bên dưới.
        owner = User(
            email=payload.owner_email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name=payload.owner_full_name,
            is_verified=True,
            is_paid=payload.plan == "paid",
            trial_ends_at=None if payload.plan == "paid" else datetime.now(UTC) + timedelta(days=settings.trial_duration_days),
        )
        db.add(owner)
        db.flush()

    topic = Topic(
        user_id=owner.id,
        name=payload.name,
        keywords=payload.keywords,
        alert_threshold=payload.alert_threshold,
        notify_enabled=payload.notify_enabled,
        notify_channel=payload.notify_channel,
        auto_assign_enabled=payload.auto_assign_enabled,
    )
    db.add(topic)
    db.flush()
    for src in payload.sources:
        db.add(Source(topic_id=topic.id, type=src.type, config=src.config))
    db.commit()
    db.refresh(topic)

    if is_new_owner:
        _send_welcome_email(owner, topic_name=topic.name, plan=payload.plan, db=db)

    # is_owner tính theo NGƯỜI GỌI (admin) chứ không phải chủ sở hữu mới — admin tạo hộ chứ không
    # sở hữu, đúng ý nghĩa field này ở mọi endpoint khác (xem _to_response).
    return _to_response(topic, admin)


def _send_welcome_email(owner: User, *, topic_name: str, plan: str, db: Session) -> None:
    """Gửi link đặt mật khẩu lần đầu — tái dùng đúng cơ chế reset_token/reset_password đã có
    (POST /auth/reset-password), chỉ khác thời hạn token (xem _WELCOME_TOKEN_EXPIRE_MINUTES)."""
    settings = get_settings()
    owner.reset_token = secrets.token_urlsafe(32)
    owner.reset_token_expires_at = datetime.now(UTC) + timedelta(minutes=_WELCOME_TOKEN_EXPIRE_MINUTES)
    db.commit()

    reset_link = f"{settings.frontend_base_url}/reset-password?token={owner.reset_token}"
    trial_note = (
        f"<p>Bạn đang dùng thử miễn phí trong {settings.trial_duration_days} ngày, "
        f"đến hết ngày {owner.trial_ends_at:%d/%m/%Y}.</p>"
        if plan == "trial" and owner.trial_ends_at
        else ""
    )
    send_email(
        to=owner.email,
        subject="Tài khoản làm việc của bạn đã sẵn sàng",
        html_body=render_email(
            heading="Tài khoản làm việc của bạn đã sẵn sàng",
            body_html=(
                f"<p>Tài khoản làm việc cho <strong>{topic_name}</strong> đã được tạo với địa chỉ "
                f"email này ({owner.email}).</p>"
                f"<p>Nhấn nút bên dưới để đặt mật khẩu và bắt đầu sử dụng "
                f"(hết hạn sau {_WELCOME_TOKEN_EXPIRE_MINUTES // 60} giờ).</p>"
                f"{trial_note}"
            ),
            cta_url=reset_link,
            cta_label="Đặt mật khẩu",
        ),
    )


@router.get("/{topic_id}", response_model=TopicResponse)
def get_topic(
    topic_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TopicResponse:
    # Thành viên cũng cần xem được chủ đề để mở dashboard; sửa/xoá vẫn chỉ chủ sở hữu (bên dưới).
    return _to_response(get_accessible_topic(topic_id, current_user, db), current_user)


@router.patch("/{topic_id}", response_model=TopicResponse)
def update_topic(
    topic_id: UUID,
    payload: TopicUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Topic:
    topic = get_owned_topic(topic_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(topic, field, value)
    db.commit()
    db.refresh(topic)
    return _to_response(topic, current_user)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    topic = get_owned_topic(topic_id, current_user, db)
    db.delete(topic)
    db.commit()


@router.post("/{topic_id}/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def add_source(
    topic_id: UUID,
    payload: SourceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Source:
    topic = get_owned_topic(topic_id, current_user, db)
    source = Source(
        topic_id=topic.id,
        type=payload.type,
        config=payload.config,
        crawl_interval_minutes=payload.crawl_interval_minutes,
        analysis_priority=payload.analysis_priority,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.patch("/{topic_id}/sources/{source_id}", response_model=SourceResponse)
def update_source(
    topic_id: UUID,
    source_id: UUID,
    payload: SourceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Source:
    topic = get_owned_topic(topic_id, current_user, db)
    source = _get_owned_source(topic, source_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return source


@router.delete("/{topic_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    topic_id: UUID,
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    topic = get_owned_topic(topic_id, current_user, db)
    source = _get_owned_source(topic, source_id, db)
    db.delete(source)
    db.commit()


@router.get("/{topic_id}/official-documents", response_model=list[OfficialDocumentResponse])
def list_official_documents(
    topic_id: UUID,
    category: str | None = Query(default=None, description="Lọc theo loại tài liệu (vd 'fee')"),
    sentiment: str | None = Query(
        default=None, description="Lọc theo sắc thái đưa tin (chỉ có nghĩa với category='news')"
    ),
    q: str | None = Query(
        default=None, min_length=1, max_length=200, description="Tìm theo từ khoá trong tiêu đề/nội dung"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OfficialDocumentResponse]:
    """Tài liệu tham chiếu (thông báo/chính sách/biểu phí/sự cố/bảo trì/sản phẩm) crawl được từ
    website chính thức ngân hàng cho chủ đề này — cùng nguồn dữ liệu Verification Agent dùng để đối
    chiếu (xem src/analysis/knowledge_base/loader.py::load_topic_documents)."""
    topic = get_accessible_topic(topic_id, current_user, db)
    query = db.query(OfficialDocument).filter(OfficialDocument.topic_id == topic.id)
    if category is not None:
        query = query.filter(OfficialDocument.category == category)
    if sentiment is not None:
        query = query.filter(OfficialDocument.sentiment == sentiment)
    if q is not None:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(
            (OfficialDocument.title.ilike(f"%{escaped}%", escape="\\"))
            | (OfficialDocument.content.ilike(f"%{escaped}%", escape="\\"))
        )
    docs = (
        query.order_by(OfficialDocument.published_at.desc().nullslast(), OfficialDocument.last_seen_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return docs


@router.get("/{topic_id}/members", response_model=list[AssigneeRef])
def list_members(
    topic_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[AssigneeRef]:
    """Danh sách người có thể được giao việc trong chủ đề: chủ sở hữu + các thành viên đã mời.

    Thành viên cũng xem được (cần để dựng dropdown giao việc), nhưng chỉ chủ sở hữu mới thêm/xoá.
    Cố ý KHÔNG có endpoint liệt kê toàn bộ user hệ thống — sẽ lộ email của người dùng không liên quan.
    """
    topic = get_accessible_topic(topic_id, current_user, db)
    member_rows = (
        db.query(User, TopicMember.department)
        .join(TopicMember, TopicMember.user_id == User.id)
        .filter(TopicMember.topic_id == topic.id)
        .all()
    )
    owner_ref = AssigneeRef(id=topic.user.id, email=topic.user.email, full_name=topic.user.full_name, department=None)
    return [owner_ref] + [
        AssigneeRef(id=u.id, email=u.email, full_name=u.full_name, department=department) for u, department in member_rows
    ]


@router.post("/{topic_id}/members", response_model=AssigneeRef, status_code=status.HTTP_201_CREATED)
def add_member(
    topic_id: UUID,
    payload: TopicMemberCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssigneeRef:
    """Thêm nhân viên vào chủ đề. Email đã có tài khoản (vd đang làm việc ở chủ đề khác) thì thêm
    thẳng làm thành viên; CHƯA có thì TẠO MỚI tài khoản luôn — cùng cơ chế admin_create_topic() dùng
    để tạo chủ sở hữu (mật khẩu ngẫu nhiên không ai biết/gõ được, người này tự đặt qua link gửi
    trong email _send_welcome_email() bên dưới). is_paid=True/trial_ends_at=None ngay từ đầu: nhân
    viên KHÔNG phải đối tượng dùng thử/thanh toán, để None thay vì reuse trial của chủ sở hữu tránh
    vô tình dính cổng chặn hết-hạn-dùng-thử ở routes_auth.py::login()."""
    topic = get_owned_topic(topic_id, current_user, db)

    user = db.query(User).filter(User.email == payload.email).first()
    is_new_user = user is None
    if is_new_user:
        user = User(
            email=payload.email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            is_verified=True,
            is_paid=True,
            trial_ends_at=None,
        )
        db.add(user)
        db.flush()
    elif user.id == topic.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Đây là chủ sở hữu chủ đề, đã có sẵn mọi quyền"
        )
    else:
        existing = db.query(TopicMember).filter(TopicMember.topic_id == topic.id, TopicMember.user_id == user.id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Người này đã là thành viên")

    db.add(TopicMember(topic_id=topic.id, user_id=user.id, department=payload.department))
    db.commit()

    if is_new_user:
        # plan="paid" chỉ để tắt đoạn ghi chú "đang dùng thử" trong email (xem _send_welcome_email)
        # — khớp đúng is_paid=True/trial_ends_at=None vừa gán ở trên, không phải nhân viên này thật
        # sự trả phí.
        _send_welcome_email(user, topic_name=topic.name, plan="paid", db=db)
    return AssigneeRef(id=user.id, email=user.email, full_name=user.full_name, department=payload.department)


@router.patch("/{topic_id}/members/{user_id}", response_model=AssigneeRef)
def update_member(
    topic_id: UUID,
    user_id: UUID,
    payload: TopicMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssigneeRef:
    """Sửa phòng ban của 1 nhân viên đã có — trước đây chỉ thêm/xoá được, không sửa (phải xoá rồi
    thêm lại, mất luôn is_new_user welcome email nếu lỡ tay)."""
    topic = get_owned_topic(topic_id, current_user, db)
    member = db.query(TopicMember).filter(TopicMember.topic_id == topic.id, TopicMember.user_id == user_id).first()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thành viên")
    member.department = payload.department
    db.commit()
    user = db.query(User).filter(User.id == user_id).one()
    return AssigneeRef(id=user.id, email=user.email, full_name=user.full_name, department=member.department)


@router.delete("/{topic_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    topic_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    topic = get_owned_topic(topic_id, current_user, db)
    member = db.query(TopicMember).filter(TopicMember.topic_id == topic.id, TopicMember.user_id == user_id).first()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thành viên")
    db.delete(member)
    db.commit()
