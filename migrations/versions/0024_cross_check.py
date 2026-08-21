"""Cross-Check Agent: phân loại độc lập lần 2 bằng model khác hẳn kiến trúc (OpenAI), CHỈ chạy khi
consensus_status ban đầu là "needs_review" — xem src/analysis/cross_check.py.

- predictions.cross_check_agreed: NULL = chưa cross-check, True/False = đã cross-check, model độc
  lập có đồng thuận hay không.
- llm_call_type thêm giá trị "cross_check" để usage tracking (llm_usage.call_type) ghi nhận đúng
  loại lượt gọi này, tách khỏi "consensus".

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("predictions", sa.Column("cross_check_agreed", sa.Boolean(), nullable=True))
    # ALTER TYPE ... ADD VALUE không chạy được trong transaction ở Postgres cũ hơn — nhưng PG 12+
    # (dự án dùng postgres:16-alpine, xem docker-compose.yml) cho phép trong cùng transaction, nên
    # không cần autocommit_block đặc biệt như 1 số hướng dẫn cũ.
    op.execute("ALTER TYPE llm_call_type ADD VALUE IF NOT EXISTS 'cross_check'")


def downgrade():
    # Không có cách xoá 1 giá trị khỏi Postgres ENUM mà không rebuild lại cả type (cần đổi tên cột
    # tạm, tạo type mới, migrate dữ liệu, đổi tên lại) — quá rủi ro cho 1 downgrade hiếm khi chạy.
    # Chỉ hoàn tác cột, giữ nguyên giá trị enum đã thêm (vô hại nếu không dùng tới).
    op.drop_column("predictions", "cross_check_agreed")
