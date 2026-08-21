"""sources: thêm giá trị enum 'tiktok' cho source_type

TikTokApifyCollector (xem src/pipeline/collectors/tiktok.py) thu thập video + comment công khai
qua Apify, cùng hướng đi đã dùng cho Facebook — cần giá trị enum mới để tạo được Source loại này.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-16
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'tiktok'")


def downgrade():
    # Postgres không hỗ trợ xoá 1 giá trị khỏi enum trực tiếp — rollback thật cần tạo lại enum mới
    # rồi migrate cột sang, ngoài phạm vi rollback thông thường (giống cách 0013_facebook_source_type
    # đã xử lý, xem migration đó).
    pass
