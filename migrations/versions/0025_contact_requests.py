"""contact_requests: lưu lại yêu cầu "Liên hệ tư vấn" từ trang giới thiệu công khai

Thay cho luồng tự đăng ký công khai đã gỡ — POST /contact giờ vừa gửi email cho platform admin
vừa lưu DB, để admin xem/đánh dấu đã xử lý qua GET/PATCH /admin/contacts (trang /admin/contacts)
thay vì chỉ trông chờ vào email (dễ bị bỏ lỡ/rơi spam).

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "contact_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("is_handled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_contact_requests_created_at", "contact_requests", ["created_at"])


def downgrade():
    op.drop_table("contact_requests")
