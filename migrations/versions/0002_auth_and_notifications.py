"""auth + notification service columns: users.reset_token, pain_points.last_notified_post_count

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("reset_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("reset_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pain_points", sa.Column("last_notified_post_count", sa.Integer, nullable=True))


def downgrade():
    op.drop_column("pain_points", "last_notified_post_count")
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "reset_token")
