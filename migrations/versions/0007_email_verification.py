"""Xác thực email khi đăng ký — chặn đăng nhập cho tới khi bấm link xác thực

Tài khoản đã tồn tại TRƯỚC tính năng này được coi là đã xác thực (server_default='true' ở bước
add_column áp dụng cho mọi dòng hiện có) — không hợp lý khoá đăng nhập của người dùng đang hoạt
động chỉ vì tính năng mới ra đời sau. Đăng ký MỚI thì mặc định chưa xác thực (đổi default sau khi
backfill xong).

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="true"))
    # Backfill xong thì đổi default — user đăng ký từ giờ trở đi mặc định chưa xác thực.
    op.alter_column("users", "is_verified", server_default="false")

    op.add_column("users", sa.Column("verification_token", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("verification_token_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("users", "verification_token_expires_at")
    op.drop_column("users", "verification_token")
    op.drop_column("users", "is_verified")
