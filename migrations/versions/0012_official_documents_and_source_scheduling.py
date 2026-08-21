"""official_documents (nguồn đối chiếu crawl từ website ngân hàng) + lịch crawl riêng theo nguồn +
điểm ưu tiên phân tích của post

Mở rộng Phase 1 của tính năng "nguồn đối chiếu chính thức": thêm loại nguồn 'bank_website' (khác hẳn
3 loại review hiện có — đây là thông báo/chính sách/biểu phí/sự cố/bảo trì/sản phẩm CHÍNH THỨC của
ngân hàng, không phải phản hồi khách hàng) nên có bảng riêng `official_documents`, không đi vào
`posts`. `sources.crawl_interval_minutes`/`last_crawled_at` cho phép từng nguồn có lịch crawl riêng
(NULL = giữ nguyên nhịp scheduler mặc định như trước, không đổi hành vi nguồn cũ).
`posts.priority_score` phục vụ sắp hàng đợi phân tích khi quota LLM có hạn.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

document_category = sa.Enum(
    "notice", "policy", "fee", "incident", "maintenance", "product", "other", name="document_category"
)


def upgrade():
    # Postgres 12+ cho phép ADD VALUE trong transaction miễn không dùng giá trị mới ngay trong cùng
    # transaction (ở đây không insert dòng nào dùng 'bank_website') — an toàn, không cần autocommit
    # block.
    op.execute("ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'bank_website'")

    op.add_column("sources", sa.Column("crawl_interval_minutes", sa.Integer(), nullable=True))
    op.add_column("sources", sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("posts", sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"))

    # KHÔNG gọi document_category.create(bind) riêng — op.create_table() bên dưới đã tự tạo type
    # Enum khi thấy cột dùng type này lần đầu; gọi thêm sẽ bị lỗi "type already exists".
    op.create_table(
        "official_documents",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", document_category, nullable=False, server_default="other"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("topic_id", "url", name="uq_official_documents_topic_url"),
    )
    op.create_index("ix_official_documents_topic_id", "official_documents", ["topic_id"])
    op.create_index("ix_official_documents_source_id", "official_documents", ["source_id"])


def downgrade():
    op.drop_index("ix_official_documents_source_id", table_name="official_documents")
    op.drop_index("ix_official_documents_topic_id", table_name="official_documents")
    op.drop_table("official_documents")
    document_category.drop(op.get_bind())

    op.drop_column("posts", "priority_score")

    op.drop_column("sources", "last_crawled_at")
    op.drop_column("sources", "crawl_interval_minutes")

    # Không thể DROP VALUE khỏi enum ở Postgres — 'bank_website' vẫn còn trong source_type sau khi
    # downgrade (hạn chế đã biết của Postgres, không phải thiếu sót của migration này).
