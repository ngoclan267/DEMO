"""posts: lưu phản hồi của nhà phát triển/ngân hàng (reply_content, reply_at)

Trước đây collector Google Play chỉ lấy nội dung + ngày đăng của review, bỏ qua hẳn
repliedAt/replyContent mà thư viện google-play-scraper trả về — nên dashboard không có chỗ nào
hiển thị được ngày ngân hàng phản hồi, dễ gây hiểu nhầm ngày hiển thị (posted_at của review) là
ngày phản hồi. App Store RSS feed công khai không có trường tương đương nên 2 cột này sẽ luôn NULL
với review từ app_store.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("posts", sa.Column("reply_content", sa.Text(), nullable=True))
    op.add_column("posts", sa.Column("reply_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("posts", "reply_at")
    op.drop_column("posts", "reply_content")
