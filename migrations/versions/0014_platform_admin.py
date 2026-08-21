"""users: thêm is_platform_admin — quyền quản trị TỔNG của nền tảng

Khác với chủ sở hữu topic (admin của riêng 1 workspace, đã có sẵn qua Topic.user_id) — đây là 1
tài khoản duy nhất/vài tài khoản có thể tạo topic THAY cho doanh nghiệp khác (kèm tạo luôn tài
khoản chủ sở hữu cho họ), xem POST /topics/admin. Không cần bảng role riêng vì chỉ có đúng 1
quyền nhị phân cho use-case này.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users", sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default="false")
    )


def downgrade():
    op.drop_column("users", "is_platform_admin")
