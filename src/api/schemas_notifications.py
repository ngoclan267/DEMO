from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # None cho contact_request — thông báo cấp nền tảng, không gắn topic nào (xem
    # src/db/models.py::Notification.topic_id).
    topic_id: UUID | None
    pain_point_id: UUID | None
    channel: str
    notification_type: str
    severity: float | None
    message: str | None
    sent_at: datetime
    read_status: str


class MarkAllReadResponse(BaseModel):
    updated_count: int
