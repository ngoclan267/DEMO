#!/usr/bin/env python3
"""Seed dữ liệu demo cho pipeline: 1 user, các Topic + Source (Google Play / App Store)
để Collector Agent có việc để chạy ngay. Idempotent — chạy lại nhiều lần không tạo trùng.

Usage:
  python scripts/seed_data.py
"""
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Console Windows mặc định dùng cp1252 (không có glyph cho ký tự tiếng Việt có dấu) — reconfigure
# trước khi print bất kỳ nội dung tiếng Việt nào, tránh UnicodeEncodeError giữa chừng script.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from src.db.models import OfficialDocument, Source, Topic, User  # noqa: E402
from src.db.session import SessionLocal  # noqa: E402

DEMO_USER_EMAIL = "demo@ai20k.local"

# Tài liệu tham chiếu RIÊNG của từng ngân hàng — cố ý seed thẳng vào official_documents (scoped theo
# topic_id) thay vì đặt trong src/analysis/knowledge_base/*.md (kho đó CHỈ dành cho văn bản áp dụng
# mọi ngân hàng, xem cảnh báo trong load_knowledge_base()). Từng có sự cố thật: 2 file này bị đặt
# nhầm vào kho toàn cục, khiến review của khách hàng TPBank bị đối chiếu nhầm với thông báo của SHB
# (và ngược lại) — xem test_global_knowledge_base_has_no_bank_specific_docs trong
# tests/test_analysis/test_knowledge_base.py.
REFERENCE_DOCS = [
    {
        "topic_name": "TPBank Mobile",
        "url": "https://tpb.vn/tin-tuc/tin-tpbank/thong-bao-cap-nhat-sth-khtc-truoc-ngay-01072025",
        "title": "Thông báo chính thức của TPBank — cập nhật sinh trắc học khuôn mặt trước 01/07/2025",
        "category": "notice",
        "published_at": datetime(2025, 7, 1, tzinfo=timezone.utc),
        "content": (
            "TPBank ra thông báo chính thức: theo Thông tư 17/2024/TT-NHNN của Ngân hàng Nhà nước, "
            "người đại diện hợp pháp của khách hàng tổ chức (doanh nghiệp) cần hoàn tất cập nhật xác "
            "thực sinh trắc học khuôn mặt (chụp ảnh giấy tờ tuỳ thân + quét khuôn mặt) qua ứng dụng "
            "TPBank Biz trước ngày 01/07/2025 để tiếp tục sử dụng dịch vụ ngân hàng điện tử của "
            "TPBank.\n\nNếu không hoàn tất trước hạn, tài khoản tổ chức sẽ bị hạn chế giao dịch điện "
            "tử tương tự cơ chế áp dụng cho tài khoản cá nhân theo Thông tư 17/2024/TT-NHNN và Thông "
            "tư 18/2024/TT-NHNN. Đây là nguồn giải thích cho các phàn nàn \"tài khoản doanh nghiệp "
            "trên TPBank Biz/TPBank Mobile bị khoá\" xuất hiện quanh mốc 01/07/2025."
        ),
    },
    {
        "topic_name": "SHB Saha Mobile Banking",
        "url": "https://www.shb.com.vn/shb-khuyen-nghi-khach-hang-som-hoan-tat-bo-sung-thong-tin-sinh-trac-hoc-theo-quy-dinh/",
        "title": "Thông báo chính thức của SHB — khuyến nghị khách hàng hoàn tất xác thực sinh trắc học",
        "category": "notice",
        "published_at": datetime(2024, 10, 30, tzinfo=timezone.utc),
        "content": (
            "Ngày 30/10/2024, Ngân hàng SHB (chủ quản ứng dụng SHB SAHA) ra thông báo chính thức: kể "
            "từ 01/01/2025, chủ tài khoản/chủ thẻ CHƯA xác thực khớp đúng giấy tờ tuỳ thân và thông "
            "tin sinh trắc học sẽ KHÔNG thể thực hiện giao dịch điện tử, đồng thời bị tạm dừng khả "
            "năng rút tiền/giao dịch khi giấy tờ tuỳ thân hết hạn.\n\nSHB khuyến nghị khách hàng chủ "
            "động hoàn tất xác thực sinh trắc học sớm qua ứng dụng SHB SAHA để tránh gián đoạn giao "
            "dịch tài chính điện tử hoặc rút tiền tại ATM sau ngày 01/01/2025.\n\nĐây là bằng chứng "
            "trực tiếp: nếu người dùng SHB SAHA phàn nàn \"tài khoản bị khoá\" quanh hoặc sau mốc "
            "01/01/2025, nhiều khả năng cao là do chưa hoàn tất xác thực sinh trắc học theo đúng "
            "thông báo này của SHB — không phải lỗi kỹ thuật của ứng dụng."
        ),
    },
]

TOPICS = [
    {
        "name": "SHB Saha Mobile Banking",
        "keywords": ["SHB", "Saha", "SHB Saha", "app SHB", "ngan hang SHB"],
        "sources": [
            # Không khai báo package_name/app_id cứng — collector tự search theo tên ngân hàng
            # rồi chọn app khớp nhất (xem GooglePlayCollector/AppStoreCollector._resolve_*).
            {"type": "google_play", "config": {"query": "SHB Saha", "lang": "vi", "country": "vn"}},
            {"type": "app_store", "config": {"query": "SHB Saha", "country": "vn"}},
        ],
    },
    {
        "name": "TPBank Mobile",
        "keywords": ["TPBank", "TPBank Mobile", "app TPBank"],
        "sources": [
            {"type": "google_play", "config": {"query": "TPBank Mobile", "lang": "vi", "country": "vn"}},
            {"type": "app_store", "config": {"query": "TPBank Mobile", "country": "vn"}},
        ],
    },
]


def get_or_create_user(session) -> User:
    user = session.query(User).filter_by(email=DEMO_USER_EMAIL).first()
    if user:
        return user
    # password_hash chỉ là placeholder — phase này chưa có auth, user demo không dùng để đăng nhập.
    user = User(email=DEMO_USER_EMAIL, password_hash="seed-only-not-a-real-login", full_name="Demo Owner")
    session.add(user)
    session.flush()
    return user


def get_or_create_topic(session, user: User, name: str, keywords: list[str]) -> Topic:
    topic = session.query(Topic).filter_by(user_id=user.id, name=name).first()
    if topic:
        return topic
    topic = Topic(user_id=user.id, name=name, keywords=keywords)
    session.add(topic)
    session.flush()
    return topic


def get_or_create_source(session, topic: Topic, source_type: str, config: dict) -> Source:
    source = session.query(Source).filter_by(topic_id=topic.id, type=source_type).first()
    if source:
        source.config = config
        source.is_active = True
        return source
    source = Source(topic_id=topic.id, type=source_type, config=config)
    session.add(source)
    session.flush()
    return source


def get_or_create_official_document(session, topic: Topic, doc: dict) -> OfficialDocument:
    """Upsert theo UNIQUE(topic_id, url) — cùng ràng buộc dùng bởi pipeline crawl thật (xem
    upsert_official_documents trong src/pipeline/processing/reference_docs.py), để tài liệu seed thủ
    công ở đây và tài liệu crawl tự động sau này không bao giờ đụng nhau."""
    existing = session.query(OfficialDocument).filter_by(topic_id=topic.id, url=doc["url"]).first()
    content_hash = hashlib.sha256(doc["content"].encode("utf-8")).hexdigest()
    if existing:
        existing.title = doc["title"]
        existing.content = doc["content"]
        existing.content_hash = content_hash
        existing.category = doc["category"]
        existing.published_at = doc["published_at"]
        return existing
    official_doc = OfficialDocument(
        topic_id=topic.id,
        url=doc["url"],
        title=doc["title"],
        content=doc["content"],
        content_hash=content_hash,
        category=doc["category"],
        published_at=doc["published_at"],
    )
    session.add(official_doc)
    session.flush()
    return official_doc


def main() -> None:
    session = SessionLocal()
    try:
        user = get_or_create_user(session)
        topics_by_name: dict[str, Topic] = {}
        for topic_def in TOPICS:
            topic = get_or_create_topic(session, user, topic_def["name"], topic_def["keywords"])
            topics_by_name[topic_def["name"]] = topic
            for source_def in topic_def["sources"]:
                get_or_create_source(session, topic, source_def["type"], source_def["config"])

        for doc in REFERENCE_DOCS:
            topic = topics_by_name.get(doc["topic_name"])
            if topic is None:
                continue
            get_or_create_official_document(session, topic, doc)

        session.commit()
        print(f"Seed xong: user={user.email}, {len(TOPICS)} topic(s), {len(REFERENCE_DOCS)} tài liệu tham chiếu")
    finally:
        session.close()


if __name__ == "__main__":
    main()
