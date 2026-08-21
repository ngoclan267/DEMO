from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.schemas_notifications import MarkAllReadResponse, NotificationResponse
from src.auth.dependencies import get_current_user
from src.db.models import Notification, User
from src.db.session import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    topic_id: UUID | None = Query(default=None),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if topic_id is not None:
        query = query.filter(Notification.topic_id == topic_id)
    if unread_only:
        query = query.filter(Notification.read_status == "unread")
    return query.order_by(Notification.sent_at.desc()).limit(limit).all()


@router.patch("/read-all", response_model=MarkAllReadResponse)
def mark_all_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MarkAllReadResponse:
    """Đánh dấu đã đọc toàn bộ thông báo CHƯA đọc của người dùng hiện tại — dùng UPDATE hàng loạt
    thay vì load từng bản ghi rồi set trong Python, vì số lượng thông báo tích lũy có thể lớn."""
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.read_status == "unread")
        .update({"read_status": "read"})
    )
    db.commit()
    return MarkAllReadResponse(updated_count=updated)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Notification:
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy notification")
    notification.read_status = "read"
    db.commit()
    db.refresh(notification)
    return notification
