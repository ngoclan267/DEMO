"""sources.type: thêm 'facebook' — nguồn phản hồi khách hàng công khai qua Apify (bên thứ ba)

Comment công khai trên bài đăng của trang/nhóm Facebook, thu thập qua Apify (không tự scrape trực
tiếp — xem docs/linkedin_facebook_scraping_research.md mục 5). Đây là nguồn PHẢN HỒI KHÁCH HÀNG
(giống google_play/app_store), khác hẳn 'bank_website' (nguồn đối chiếu chính thức) — đi vào bảng
`posts` như bình thường, không cần bảng riêng.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-11
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    # Postgres 12+ cho phép ADD VALUE trong transaction miễn không dùng giá trị mới ngay trong cùng
    # transaction — an toàn, không cần autocommit block (giống cách làm ở migration 0012).
    op.execute("ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'facebook'")


def downgrade():
    # Không thể DROP VALUE khỏi enum ở Postgres — 'facebook' vẫn còn trong source_type sau khi
    # downgrade (hạn chế đã biết của Postgres, không phải thiếu sót của migration này).
    pass
