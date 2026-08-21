"""llm_usage: ghi nhận token đã dùng cho mỗi lượt gọi LLM thành công

Dùng để admin xem mức tiêu thụ + chi phí ƯỚC TÍNH theo tài khoản (xem src/analysis/pricing.py).
user_id/topic_id lưu trực tiếp (denormalized) với ondelete="SET NULL" — xoá topic/user không mất
lịch sử tiêu thụ đã ghi nhận, chỉ mất đường link truy vết thuộc về ai.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "llm_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "call_type",
            sa.Enum(
                "classification",
                "verification",
                "consensus",
                "pain_point_description",
                "news_sentiment",
                name="llm_call_type",
            ),
            nullable=False,
        ),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_llm_usage_user_id", "llm_usage", ["user_id"])
    op.create_index("ix_llm_usage_topic_id", "llm_usage", ["topic_id"])
    op.create_index("ix_llm_usage_created_at", "llm_usage", ["created_at"])


def downgrade():
    op.drop_table("llm_usage")
    op.execute("DROP TYPE IF EXISTS llm_call_type")
