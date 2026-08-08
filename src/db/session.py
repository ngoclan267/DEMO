"""SQLite engine/session dong bo cho API layer (xem src/db/models.py)."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings
from src.db.models import Base


def _make_engine():
    settings = get_settings()
    db_path = Path(settings.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_pain_point_columns()
    _ensure_post_classification_columns()


def _ensure_pain_point_columns() -> None:
    """create_all khong tu them cot vao bang da ton tai - can migration cong
    them thu cong cho DB that da tao truoc khi co cac cot Respond (status,
    assignee, resolution_notes, resolved_at). An toan: chi ADD COLUMN, khong
    dung Alembic vi project chua dung migration tool nao."""
    migrations = {
        "status": "ALTER TABLE pain_points ADD COLUMN status VARCHAR(20) DEFAULT 'open'",
        "assignee": "ALTER TABLE pain_points ADD COLUMN assignee VARCHAR(255)",
        "resolution_notes": "ALTER TABLE pain_points ADD COLUMN resolution_notes TEXT",
        "resolved_at": "ALTER TABLE pain_points ADD COLUMN resolved_at DATETIME",
        "topic_label": "ALTER TABLE pain_points ADD COLUMN topic_label VARCHAR(50)",
    }
    with engine.connect() as conn:
        existing_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(pain_points)")}
        for column, ddl in migrations.items():
            if column not in existing_cols:
                conn.exec_driver_sql(ddl)
        conn.commit()


def _ensure_post_classification_columns() -> None:
    """ADD COLUMN cho sentiment/topic_label/severity_score tren bang posts da
    ton tai truoc do - dung de luu ket qua Classification Agent ngay tren Post
    thay vi phai goi lai LLM moi lan ve bieu do xu huong (xem repository.get_topic_trend)."""
    migrations = {
        "sentiment": "ALTER TABLE posts ADD COLUMN sentiment VARCHAR(20)",
        "topic_label": "ALTER TABLE posts ADD COLUMN topic_label VARCHAR(50)",
        "severity_score": "ALTER TABLE posts ADD COLUMN severity_score FLOAT",
    }
    with engine.connect() as conn:
        existing_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(posts)")}
        for column, ddl in migrations.items():
            if column not in existing_cols:
                conn.exec_driver_sql(ddl)
        conn.commit()


def get_session() -> Session:
    return SessionLocal()
