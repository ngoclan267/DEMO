"""pain_points: cho phép quản lý tự đặt hạn xử lý (SLA) riêng, không bị auto-recompute ghi đè

Trước đây due_at hoàn toàn do máy tính lại mỗi chu kỳ phân tích (xem
src/analysis/pain_point.py::_upsert_pain_point), nên sửa trực tiếp cũng bị ghi đè ở chu kỳ sau.
due_at_overridden là cờ nguồn chân lý: True thì auto-recompute bỏ qua case này.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    # server_default="false" áp dụng cho toàn bộ dòng cũ luôn đúng — chưa từng có ai đặt hạn thủ
    # công trước migration này nên không cần backfill riêng.
    op.add_column(
        "pain_points", sa.Column("due_at_overridden", sa.Boolean(), nullable=False, server_default="false")
    )


def downgrade():
    op.drop_column("pain_points", "due_at_overridden")
