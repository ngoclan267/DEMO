"""users.username — tên đăng nhập duy nhất, đăng nhập được bằng username hoặc email

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # nullable=True: các tài khoản đã tạo trước khi có tính năng này không có username. Postgres
    # cho phép nhiều dòng NULL trong cột UNIQUE nên ràng buộc duy nhất vẫn đúng với user mới.
    op.add_column("users", sa.Column("username", sa.String(length=30), nullable=True))
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_column("users", "username")
