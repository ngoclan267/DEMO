"""posts: source_url — link trực tiếp tới bài viết/comment gốc trên nền tảng nguồn

Facebook (khác Google Play/App Store) trả về permalink thật cho từng bài viết/comment — trước đây
không có chỗ lưu nên người dùng không bấm xem được bài gốc trên Facebook, chỉ xem được nội dung đã
crawl. NULL với mọi nguồn khác (không có permalink từng review riêng).

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("posts", sa.Column("source_url", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("posts", "source_url")
