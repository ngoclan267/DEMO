"""sources.type: thêm 'news_article'; official_documents.category: thêm 'news'

Thu thập bài báo/tin tức nhắc tới ngân hàng qua Apify (nhà cung cấp thu thập dữ liệu bên thứ ba,
cùng hướng đi đã chọn cho Facebook — xem docs/linkedin_facebook_scraping_research.md mục 5), KHÔNG
tự scrape trực tiếp. Bài báo là tin BÊN THỨ BA (khác 'bank_website' — văn bản CHÍNH THỨC của ngân
hàng) nên vẫn đi vào bảng official_documents (tái dùng schema/endpoint có sẵn) nhưng gắn
category='news' và bị loại trừ khỏi knowledge base mà Verification Agent dùng để đối chiếu (xem
src/analysis/knowledge_base/loader.py::load_topic_documents) — chỉ hiển thị cho người dùng xem,
không tham gia suy luận AI.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-15
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    # Postgres 12+ cho phép ADD VALUE trong transaction miễn không dùng giá trị mới ngay trong cùng
    # transaction — an toàn, không cần autocommit block (giống migration 0012/0013).
    op.execute("ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'news_article'")
    op.execute("ALTER TYPE document_category ADD VALUE IF NOT EXISTS 'news'")


def downgrade():
    # Không thể DROP VALUE khỏi enum ở Postgres — các giá trị vẫn còn sau khi downgrade (hạn chế đã
    # biết của Postgres, không phải thiếu sót của migration này, xem migration 0013).
    pass
