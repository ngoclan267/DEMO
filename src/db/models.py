"""
SQLAlchemy ORM models - luu tru that ket qua crawl/pipeline (thay the mock_data.py).
Dung SQLite dong bo (xem src/db/session.py) de khong can Docker/Postgres cho MVP;
schema tuong ung 1-1 voi cac Pydantic model trong src/models/schemas.py.
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TopicORM(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(255))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    source_configs: Mapped[dict] = mapped_column(JSON, default=dict)
    alert_threshold: Mapped[int] = mapped_column(Integer, default=10)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PostORM(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("content_hash", name="uq_posts_content_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(String(36), index=True)
    source: Mapped[str] = mapped_column(String(50))
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime] = mapped_column(DateTime)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    # --- Ket qua Classification Agent (dung cho GET /topics/{id}/trend) ---
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    topic_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    severity_score: Mapped[float | None] = mapped_column(Float, nullable=True)


class PainPointORM(Base):
    __tablename__ = "pain_points"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(500))
    topic_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    post_count: Mapped[int] = mapped_column(Integer)
    trend: Mapped[str] = mapped_column(String(10))
    severity: Mapped[str] = mapped_column(String(20))
    verification_status: Mapped[str] = mapped_column(String(20))
    confidence_score: Mapped[float] = mapped_column(Float)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    sample_posts: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # --- Respond (vong doi xu ly - xem PainPointUpdate trong schemas.py) ---
    status: Mapped[str] = mapped_column(String(20), default="open")
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NotificationORM(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(String(36), index=True)
    pain_point_id: Mapped[str] = mapped_column(String(36))
    channel: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(500))
    message: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
