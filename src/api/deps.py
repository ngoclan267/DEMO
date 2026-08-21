from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.db.models import Topic, TopicMember, User


def get_owned_topic(topic_id: UUID, current_user: User, db: Session) -> Topic:
    """CHỈ chủ sở hữu. Dùng cho thao tác quản trị chủ đề: sửa, xoá, quản lý nguồn, quản lý thành viên."""
    topic = db.query(Topic).filter(Topic.id == topic_id, Topic.user_id == current_user.id).first()
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy topic")
    return topic


def get_accessible_topic(topic_id: UUID, current_user: User, db: Session) -> Topic:
    """Chủ sở hữu HOẶC thành viên được mời. Dùng cho xem dashboard và xử lý case.

    Trả 404 (không phải 403) khi không có quyền — không tiết lộ chủ đề đó có tồn tại hay không,
    giữ nguyên hành vi cũ của get_owned_topic."""
    topic = (
        db.query(Topic)
        .outerjoin(TopicMember, TopicMember.topic_id == Topic.id)
        .filter(
            Topic.id == topic_id,
            (Topic.user_id == current_user.id) | (TopicMember.user_id == current_user.id),
        )
        .first()
    )
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy topic")
    return topic


def is_topic_participant(topic: Topic, user_id: UUID, db: Session) -> bool:
    """Người này có thuộc chủ đề không (chủ sở hữu hoặc thành viên) — dùng để chặn giao việc cho
    người ngoài chủ đề."""
    if topic.user_id == user_id:
        return True
    return (
        db.query(TopicMember).filter(TopicMember.topic_id == topic.id, TopicMember.user_id == user_id).first()
        is not None
    )
