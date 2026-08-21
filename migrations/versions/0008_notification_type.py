"""notifications.notification_type — phân biệt cảnh báo vượt ngưỡng / được giao việc / đã xử lý xong

Cần để frontend hiện icon khác nhau và mở đường lọc theo loại sau này. Dữ liệu cũ (chỉ có đường
cảnh báo vượt ngưỡng — xem check_and_notify) backfill là 'threshold_alert'.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

notification_type = sa.Enum("threshold_alert", "assigned", "resolved", name="notification_type")


def upgrade():
    notification_type.create(op.get_bind())
    op.add_column(
        "notifications",
        sa.Column("notification_type", notification_type, nullable=False, server_default="threshold_alert"),
    )


def downgrade():
    op.drop_column("notifications", "notification_type")
    notification_type.drop(op.get_bind())
