"""Thành viên chủ đề + vòng đời xử lý case (SLA)

Hai phần liên quan nhau nên đi chung: giao việc cho ai đó chỉ có nghĩa khi chủ đề có nhiều người.

  - topic_members     : đồng nghiệp được mời vào chủ đề (chủ sở hữu vẫn là Topic.user_id)
  - pain_points.*     : vòng đời new/in_progress/resolved/duplicate/ignored + người phụ trách + hạn SLA
  - pain_point_events : nhật ký ai đổi trạng thái gì, lúc nào

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

lifecycle_status_type = sa.Enum(
    "new", "in_progress", "resolved", "duplicate", "ignored", name="lifecycle_status_type"
)


def upgrade():
    op.create_table(
        "topic_members",
        sa.Column("topic_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("topic_id", "user_id"),
    )

    lifecycle_status_type.create(op.get_bind())
    op.add_column(
        "pain_points",
        sa.Column("lifecycle_status", lifecycle_status_type, nullable=False, server_default="new"),
    )
    op.add_column("pain_points", sa.Column("assigned_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("pain_points", sa.Column("department", sa.String(length=100), nullable=True))
    op.add_column("pain_points", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pain_points", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "pain_points", sa.Column("duplicate_of_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("pain_points", sa.Column("lifecycle_note", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_pain_points_assigned_user", "pain_points", "users", ["assigned_user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_pain_points_duplicate_of", "pain_points", "pain_points", ["duplicate_of_id"], ["id"], ondelete="SET NULL"
    )

    op.create_table(
        "pain_point_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pain_point_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["pain_point_id"], ["pain_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pain_point_events_pain_point_id"), "pain_point_events", ["pain_point_id"])

    # Backfill hạn SLA cho pain point đã tồn tại. Nếu không làm, mọi case cũ sẽ hiện "chưa có hạn"
    # cho tới lần chạy Pain Point Agent kế tiếp — mà lần đó phụ thuộc quota LLM, có thể vài ngày sau.
    # Ngưỡng phải khớp src/sla.py (nghiêm trọng >=0.67: 24h, trung bình >=0.34: 72h, nhẹ: 7 ngày).
    op.execute(
        """
        UPDATE pain_points SET due_at = created_at + (
            CASE
                WHEN COALESCE(severity_avg, 0) >= 0.67 THEN INTERVAL '24 hours'
                WHEN COALESCE(severity_avg, 0) >= 0.34 THEN INTERVAL '72 hours'
                ELSE INTERVAL '168 hours'
            END
        )
        WHERE due_at IS NULL
        """
    )


def downgrade():
    op.drop_index(op.f("ix_pain_point_events_pain_point_id"), table_name="pain_point_events")
    op.drop_table("pain_point_events")

    op.drop_constraint("fk_pain_points_duplicate_of", "pain_points", type_="foreignkey")
    op.drop_constraint("fk_pain_points_assigned_user", "pain_points", type_="foreignkey")
    for column in (
        "lifecycle_note",
        "duplicate_of_id",
        "resolved_at",
        "due_at",
        "department",
        "assigned_user_id",
        "lifecycle_status",
    ):
        op.drop_column("pain_points", column)
    lifecycle_status_type.drop(op.get_bind())

    op.drop_table("topic_members")
