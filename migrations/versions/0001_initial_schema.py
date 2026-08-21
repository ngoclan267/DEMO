"""initial schema: users, topics, sources, posts, predictions, pain_points, pain_point_posts, notifications

Revision ID: 0001
Revises:
Create Date: 2026-08-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')  # cho gen_random_uuid()

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("keywords", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("alert_threshold", sa.Integer, nullable=False, server_default="10"),
        sa.Column("notify_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.Enum("active", "archived", name="topic_status"), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_topics_user_id", "topics", ["user_id"])

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Enum("google_play", "app_store", "linkedin", name="source_type"), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_sources_topic_id", "sources", ["topic_id"])

    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("raw_content", sa.Text, nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="vi"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_duplicate", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_spam", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.Enum("raw", "cleaned", name="post_status"), nullable=False, server_default="raw"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("source_id", "external_id", name="uq_posts_source_external_id"),
    )
    op.create_index("ix_posts_topic_id", "posts", ["topic_id"])
    op.create_index("ix_posts_source_id", "posts", ["source_id"])

    op.create_table(
        "predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("sentiment", sa.Enum("positive", "neutral", "negative", name="sentiment_type"), nullable=True),
        sa.Column("topic_label", sa.String(50), nullable=True),
        sa.Column("severity_score", sa.Float, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_status", sa.Enum("verified", "unverified", "conflicting", name="verification_status_type"), nullable=True),
        sa.Column("reference_sources", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("verification_confidence", sa.Float, nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consensus_status", sa.Enum("confirmed", "needs_review", "dismissed", name="consensus_status_type"), nullable=True),
        sa.Column("final_confidence", sa.Float, nullable=True),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column("consensus_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "pain_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("post_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("trend", sa.Enum("increasing", "stable", "decreasing", name="trend_type"), nullable=True),
        sa.Column("sources", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("severity_avg", sa.Float, nullable=True),
        sa.Column("confidence_avg", sa.Float, nullable=True),
        sa.Column("status", sa.Enum("unverified", "verified", "needs_review", name="painpoint_status"), nullable=False, server_default="unverified"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_pain_points_topic_id", "pain_points", ["topic_id"])

    op.create_table(
        "pain_point_posts",
        sa.Column("pain_point_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pain_points.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("is_sample", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pain_point_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pain_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.Enum("email", "web", "both", name="notification_channel"), nullable=False),
        sa.Column("severity", sa.Float, nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("read_status", sa.Enum("unread", "read", name="read_status_type"), nullable=False, server_default="unread"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_topic_id", "notifications", ["topic_id"])
    op.create_index("ix_notifications_pain_point_id", "notifications", ["pain_point_id"])


def downgrade():
    op.drop_table("notifications")
    op.drop_table("pain_point_posts")
    op.drop_table("pain_points")
    op.drop_table("predictions")
    op.drop_table("posts")
    op.drop_table("sources")
    op.drop_table("topics")
    op.drop_table("users")

    for enum_name in [
        "topic_status", "source_type", "post_status", "sentiment_type",
        "verification_status_type", "consensus_status_type", "trend_type",
        "painpoint_status", "notification_channel", "read_status_type",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
