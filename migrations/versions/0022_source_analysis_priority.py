"""sources.analysis_priority: trọng số ưu tiên phân tích do doanh nghiệp tự đặt cho từng nguồn

Mặc định 1 = mọi nguồn ngang nhau (round-robin đều, xem rank_within_source trong
src/analysis/runner.py). Số lớn hơn được chọn vào batch phân tích thường xuyên hơn theo tỷ lệ,
không bao giờ về 0 lượt — không phải thứ tự cứng "xong nguồn A mới tới nguồn B".

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sources",
        sa.Column("analysis_priority", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade():
    op.drop_column("sources", "analysis_priority")
