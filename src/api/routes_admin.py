from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.analysis.pricing import estimate_cost_usd
from src.api.schemas_admin import (
    AdminContactSummary,
    AdminContactUpdate,
    AdminTopicSummary,
    AdminUserDetail,
    AdminUserSummary,
    AdminUserUpdate,
    AdminUserUsageSummary,
)
from src.auth.dependencies import get_platform_admin
from src.config import get_settings
from src.db.models import ContactRequest, LLMUsage, PainPoint, Post, Source, Topic, User
from src.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


def _trial_call_limit_for(user: User) -> int | None:
    """None nếu không phải tài khoản dùng thử — chỉ tài khoản is_paid=False VÀ có trial_ends_at
    (do platform admin tạo, xem POST /topics/admin) mới bị áp trần lượt gọi AI miễn phí, khớp đúng
    điều kiện kiểm tra ở routes_auth.py::login."""
    if user.is_paid or user.trial_ends_at is None:
        return None
    return get_settings().trial_analysis_call_limit

# (model, input_tokens, output_tokens, call_count) — dùng chung cho cả GET /admin/users (gộp theo
# user) lẫn GET /admin/users/{id} (gộp theo topic), tránh viết lại logic quy đổi chi phí 2 nơi.
_UsageRow = tuple[str, int, int, int]


def _build_usage_summary(rows: list[_UsageRow]) -> AdminUserUsageSummary:
    total_input = sum(r[1] for r in rows)
    total_output = sum(r[2] for r in rows)
    call_count = sum(r[3] for r in rows)
    cost = 0.0
    has_unpriced = False
    for model, input_tokens, output_tokens, _ in rows:
        estimated = estimate_cost_usd(model, input_tokens, output_tokens)
        if estimated is None:
            has_unpriced = True
        else:
            cost += estimated
    return AdminUserUsageSummary(
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        call_count=call_count,
        estimated_cost_usd=cost,
        has_unpriced_usage=has_unpriced,
    )


def _get_admin_user(user_id: UUID, db: Session) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản")
    return user


@router.get("/users", response_model=list[AdminUserSummary])
def list_users(
    q: str | None = Query(default=None, min_length=1, max_length=200, description="Tìm theo email/tên"),
    admin: User = Depends(get_platform_admin),
    db: Session = Depends(get_db),
) -> list[AdminUserSummary]:
    """Toàn bộ tài khoản trên nền tảng, kèm số topic đang có + mức tiêu thụ token/chi phí ước tính
    (gộp mọi topic của tài khoản đó) — CHỈ platform admin gọi được (xem get_platform_admin)."""
    query = db.query(User)
    if q is not None:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(
            (User.email.ilike(f"%{escaped}%", escape="\\")) | (User.full_name.ilike(f"%{escaped}%", escape="\\"))
        )
    users = query.order_by(User.created_at.desc()).all()

    topic_counts = dict(db.query(Topic.user_id, func.count(Topic.id)).group_by(Topic.user_id).all())

    usage_by_user: dict[UUID, list[_UsageRow]] = defaultdict(list)
    usage_rows = (
        db.query(
            LLMUsage.user_id,
            LLMUsage.model,
            func.coalesce(func.sum(LLMUsage.input_tokens), 0),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0),
            func.count(LLMUsage.id),
        )
        .filter(LLMUsage.user_id.isnot(None))
        .group_by(LLMUsage.user_id, LLMUsage.model)
        .all()
    )
    for user_id, model, input_tokens, output_tokens, call_count in usage_rows:
        usage_by_user[user_id].append((model, input_tokens, output_tokens, call_count))

    return [
        AdminUserSummary(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            username=u.username,
            is_platform_admin=u.is_platform_admin,
            is_paid=u.is_paid,
            is_verified=u.is_verified,
            trial_ends_at=u.trial_ends_at,
            created_at=u.created_at,
            topic_count=topic_counts.get(u.id, 0),
            usage=_build_usage_summary(usage_by_user.get(u.id, [])),
            trial_analysis_call_limit=_trial_call_limit_for(u),
        )
        for u in users
    ]


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail(user_id: UUID, admin: User = Depends(get_platform_admin), db: Session = Depends(get_db)) -> AdminUserDetail:
    """Chi tiết 1 tài khoản: thông tin cơ bản + TOÀN BỘ topic đang sở hữu (không tính topic được
    mời làm thành viên — đây là góc nhìn "tài khoản này VẬN HÀNH gì", khác GET /topics của chính
    user đó vốn gộp cả 2 loại), kèm mức tiêu thụ token/chi phí tách riêng theo từng topic."""
    user = _get_admin_user(user_id, db)
    topics = db.query(Topic).filter(Topic.user_id == user.id).order_by(Topic.created_at.desc()).all()

    source_counts = dict(
        db.query(Source.topic_id, func.count(Source.id)).filter(Source.topic_id.in_([t.id for t in topics])).group_by(Source.topic_id).all()
    )
    post_counts = dict(
        db.query(Post.topic_id, func.count(Post.id)).filter(Post.topic_id.in_([t.id for t in topics])).group_by(Post.topic_id).all()
    )
    pain_point_counts = dict(
        db.query(PainPoint.topic_id, func.count(PainPoint.id))
        .filter(PainPoint.topic_id.in_([t.id for t in topics]))
        .group_by(PainPoint.topic_id)
        .all()
    )

    usage_by_topic: dict[UUID, list[_UsageRow]] = defaultdict(list)
    usage_rows = (
        db.query(
            LLMUsage.topic_id,
            LLMUsage.model,
            func.coalesce(func.sum(LLMUsage.input_tokens), 0),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0),
            func.count(LLMUsage.id),
        )
        .filter(LLMUsage.topic_id.in_([t.id for t in topics]))
        .group_by(LLMUsage.topic_id, LLMUsage.model)
        .all()
    )
    for topic_id, model, input_tokens, output_tokens, call_count in usage_rows:
        usage_by_topic[topic_id].append((model, input_tokens, output_tokens, call_count))

    topic_summaries = [
        AdminTopicSummary(
            id=t.id,
            name=t.name,
            status=t.status,
            created_at=t.created_at,
            source_count=source_counts.get(t.id, 0),
            post_count=post_counts.get(t.id, 0),
            pain_point_count=pain_point_counts.get(t.id, 0),
            usage=_build_usage_summary(usage_by_topic.get(t.id, [])),
        )
        for t in topics
    ]
    all_usage_rows = [row for rows in usage_by_topic.values() for row in rows]

    return AdminUserDetail(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        username=user.username,
        is_platform_admin=user.is_platform_admin,
        is_paid=user.is_paid,
        is_verified=user.is_verified,
        trial_ends_at=user.trial_ends_at,
        created_at=user.created_at,
        topic_count=len(topics),
        usage=_build_usage_summary(all_usage_rows),
        trial_analysis_call_limit=_trial_call_limit_for(user),
        topics=topic_summaries,
    )


@router.patch("/users/{user_id}", response_model=AdminUserSummary)
def update_user(
    user_id: UUID, payload: AdminUserUpdate, admin: User = Depends(get_platform_admin), db: Session = Depends(get_db)
) -> AdminUserSummary:
    user = _get_admin_user(user_id, db)
    changes = payload.model_dump(exclude_unset=True)

    # Tự thu hồi quyền admin của CHÍNH MÌNH dễ dẫn tới khoá luôn lối vào trang quản trị (không còn
    # ai gọi được get_platform_admin để cấp lại) — chặn ở đây, phải nhờ admin KHÁC thu hồi hộ.
    if changes.get("is_platform_admin") is False and user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không thể tự thu hồi quyền quản trị của chính mình")

    for field in ("full_name", "is_paid", "is_platform_admin", "trial_ends_at"):
        if field in changes:
            setattr(user, field, changes[field])
    db.commit()
    db.refresh(user)

    topic_count = db.query(func.count(Topic.id)).filter(Topic.user_id == user.id).scalar() or 0
    usage_rows = (
        db.query(
            LLMUsage.model,
            func.coalesce(func.sum(LLMUsage.input_tokens), 0),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0),
            func.count(LLMUsage.id),
        )
        .filter(LLMUsage.user_id == user.id)
        .group_by(LLMUsage.model)
        .all()
    )
    return AdminUserSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        username=user.username,
        is_platform_admin=user.is_platform_admin,
        is_paid=user.is_paid,
        is_verified=user.is_verified,
        trial_ends_at=user.trial_ends_at,
        created_at=user.created_at,
        topic_count=topic_count,
        usage=_build_usage_summary(list(usage_rows)),
        trial_analysis_call_limit=_trial_call_limit_for(user),
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, admin: User = Depends(get_platform_admin), db: Session = Depends(get_db)) -> None:
    """Xoá tài khoản — CASCADE xoá luôn toàn bộ topic/post/pain point của tài khoản này (xem
    ondelete="CASCADE" trên Topic.user_id), không thể khôi phục. llm_usage giữ lại (ondelete="SET
    NULL") để không mất lịch sử tiêu thụ đã ghi nhận, chỉ mất đường link về user đã xoá."""
    user = _get_admin_user(user_id, db)
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không thể tự xoá chính mình")
    db.delete(user)
    db.commit()


@router.get("/contacts", response_model=list[AdminContactSummary])
def list_contact_requests(
    handled: bool | None = Query(default=None, description="Lọc theo đã xử lý hay chưa"),
    admin: User = Depends(get_platform_admin),
    db: Session = Depends(get_db),
) -> list[ContactRequest]:
    """Toàn bộ yêu cầu "Liên hệ tư vấn" gửi từ trang giới thiệu công khai (xem POST /contact) —
    nơi xem lại KHÔNG PHỤ THUỘC vào email có tới nơi hay không (xem ContactRequest trong
    src/db/models.py). Mới nhất lên đầu — yêu cầu chưa xử lý là thứ cần chú ý nhất, hợp lý khi hiện
    trước."""
    query = db.query(ContactRequest)
    if handled is not None:
        query = query.filter(ContactRequest.is_handled.is_(handled))
    return query.order_by(ContactRequest.created_at.desc()).all()


@router.patch("/contacts/{contact_id}", response_model=AdminContactSummary)
def update_contact_request(
    contact_id: UUID,
    payload: AdminContactUpdate,
    admin: User = Depends(get_platform_admin),
    db: Session = Depends(get_db),
) -> ContactRequest:
    """Đánh dấu đã xử lý/chưa xử lý — trạng thái đơn giản duy nhất cần theo dõi cho 1 lượt liên hệ
    (không cần vòng đời nhiều bước như PainPoint.lifecycle_status)."""
    contact = db.get(ContactRequest, contact_id)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy yêu cầu liên hệ")
    contact.is_handled = payload.is_handled
    db.commit()
    db.refresh(contact)
    return contact
