"""pain_points.is_priority: doanh nghiệp tự đánh dấu pain point nào cấp thiết nhất với họ

Mặc định False — không đánh dấu thì danh sách pain point sắp xếp mặc định theo severity_avg (mức
độ nghiêm trọng, đại diện cho "quan trọng với 1 ngân hàng" — rủi ro/tuân thủ/ảnh hưởng khách hàng,
không phải chỉ số lượng phản hồi). Pain point được đánh dấu is_priority=True luôn đứng ĐẦU danh
sách bất kể severity, vì đây là lựa chọn CHỦ ĐỘNG của doanh nghiệp, ưu tiên hơn xếp hạng tự động.

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "pain_points",
        sa.Column("is_priority", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("pain_points", "is_priority")
