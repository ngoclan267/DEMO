"""Thông báo trong hệ thống khi có yêu cầu liên hệ mới — trước đây routes_contact.py CHỈ gửi email
cho platform admin, không có gì hiện trên chuông thông báo trong app.

- notifications.topic_id: đổi thành NULLABLE — yêu cầu liên hệ không gắn với topic nào (doanh
  nghiệp CHƯA có tài khoản/chủ đề lúc gửi form "Liên hệ tư vấn"). Mọi notification_type khác vẫn
  luôn có topic_id, cột chỉ nới lỏng ràng buộc, không đổi hành vi các loại thông báo hiện có.
- notification_type thêm giá trị "contact_request".

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("notifications", "topic_id", existing_type=sa.dialects.postgresql.UUID(as_uuid=True), nullable=True)
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'contact_request'")


def downgrade():
    # Không có cách xoá giá trị khỏi Postgres ENUM mà không rebuild lại cả type — chỉ hoàn tác cột
    # nullable (giả định không có row nào thật sự NULL lúc downgrade, đúng tiền lệ 0024/0027).
    op.alter_column("notifications", "topic_id", existing_type=sa.dialects.postgresql.UUID(as_uuid=True), nullable=False)
