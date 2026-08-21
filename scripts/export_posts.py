#!/usr/bin/env python3
"""Xuất toàn bộ bảng `posts` ra CSV để xem/so sánh thủ công (vd trước và sau một chu kỳ crawl
để xác nhận có review mới được lưu vào DB hay không).

Usage:
  python scripts/export_posts.py
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.models import Post, Source, Topic  # noqa: E402
from src.db.session import SessionLocal  # noqa: E402

EXPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "exports"

COLUMNS = [
    "id",
    "topic",
    "source_type",
    "external_id",
    "content",
    "language",
    "is_spam",
    "status",
    "posted_at",
    "collected_at",
    "created_at",
]


def main() -> None:
    session = SessionLocal()
    try:
        rows = (
            session.query(Post, Topic.name, Source.type)
            .join(Topic, Post.topic_id == Topic.id)
            .outerjoin(Source, Post.source_id == Source.id)
            .order_by(Post.collected_at.desc())
            .all()
        )

        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = EXPORT_DIR / f"posts_{timestamp}.csv"

        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(COLUMNS)
            for post, topic_name, source_type in rows:
                writer.writerow(
                    [
                        post.id,
                        topic_name,
                        source_type,
                        post.external_id,
                        post.content,
                        post.language,
                        post.is_spam,
                        post.status,
                        post.posted_at,
                        post.collected_at,
                        post.created_at,
                    ]
                )

        print(f"Đã xuất {len(rows)} post ra: {out_path}")

        by_source: dict[str, int] = {}
        for _post, topic_name, source_type in rows:
            key = f"{topic_name} / {source_type}"
            by_source[key] = by_source.get(key, 0) + 1
        print("\nTổng theo nguồn:")
        for key, count in sorted(by_source.items()):
            print(f"  {key}: {count}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
