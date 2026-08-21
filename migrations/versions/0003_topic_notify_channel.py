"""topics.notify_channel — per-topic choice of email/web/both for Notification Service

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

notify_channel_type = sa.Enum("email", "web", "both", name="notify_channel_type")


def upgrade():
    notify_channel_type.create(op.get_bind())
    op.add_column(
        "topics",
        sa.Column("notify_channel", notify_channel_type, nullable=False, server_default="both"),
    )


def downgrade():
    op.drop_column("topics", "notify_channel")
    notify_channel_type.drop(op.get_bind())
