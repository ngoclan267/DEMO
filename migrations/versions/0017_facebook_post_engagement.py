"""posts: số liệu tương tác Facebook (like/comment/share) + quan hệ bài viết-comment; predictions:
is_question

FacebookApifyCollector trước đây chỉ crawl COMMENT (không có bài viết gốc, không có số liệu tương
tác). Nay crawl cả bài viết (kèm like/comment/share do Facebook đếm) lẫn comment của từng bài, nên
cần: (1) 3 cột số liệu tương tác trên `posts` — NULL với mọi nguồn khác Facebook; (2) `parent_post_id`
tự tham chiếu `posts.id` để 1 comment biết nó thuộc bài viết nào (NULL = bản ghi độc lập, áp dụng
cho mọi nguồn khác và cả bài viết Facebook gốc); (3) `predictions.is_question` — cờ Classification
Agent đánh dấu nội dung là câu hỏi/thắc mắc của khách, tách biệt khỏi sentiment sẵn có (xem
src/analysis/schemas.py::ClassificationResult).

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("posts", sa.Column("like_count", sa.Integer(), nullable=True))
    op.add_column("posts", sa.Column("comment_count", sa.Integer(), nullable=True))
    op.add_column("posts", sa.Column("share_count", sa.Integer(), nullable=True))
    op.add_column("posts", sa.Column("parent_post_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_posts_parent_post_id", "posts", "posts", ["parent_post_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_posts_parent_post_id", "posts", ["parent_post_id"])

    op.add_column("predictions", sa.Column("is_question", sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column("predictions", "is_question")

    op.drop_index("ix_posts_parent_post_id", table_name="posts")
    op.drop_constraint("fk_posts_parent_post_id", "posts", type_="foreignkey")
    op.drop_column("posts", "parent_post_id")
    op.drop_column("posts", "share_count")
    op.drop_column("posts", "comment_count")
    op.drop_column("posts", "like_count")
