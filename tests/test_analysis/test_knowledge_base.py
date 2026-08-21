import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.analysis.knowledge_base.loader import (
    KnowledgeDoc,
    format_knowledge_base_for_prompt,
    load_knowledge_base,
    load_topic_documents,
    select_relevant_docs,
)
from src.config import get_settings
from src.db.models import Base, OfficialDocument, Topic, User

EXPECTED_DOC_IDS = {
    "sbv-decision-2345",
    "circular-17-2024",
    "circular-18-2024",
}


def test_global_knowledge_base_has_no_bank_specific_docs():
    """Regression test cho sự cố thật: thông báo riêng của SHB từng bị đặt nhầm vào kho toàn cục,
    khiến review của khách hàng TPBank bị đối chiếu (và match) với thông báo của SHB. Kho toàn cục
    (load_knowledge_base) chỉ được chứa văn bản áp dụng cho MỌI ngân hàng (quy định NHNN) — tài liệu
    riêng 1 ngân hàng phải nằm trong official_documents, scoped theo topic_id (xem
    test_load_topic_documents_scopes_by_topic bên dưới)."""
    docs = load_knowledge_base()
    for doc in docs:
        assert "nhnn" in doc.url.lower() or "sbv" in doc.url.lower() or "thuvienphapluat" in doc.url.lower(), (
            f"Tài liệu '{doc.id}' trong kho toàn cục trông như văn bản riêng của 1 ngân hàng cụ thể "
            "— kiểm tra lại có nên nằm ở đây hay không (xem docstring load_knowledge_base())."
        )


def test_loads_all_reference_docs():
    docs = load_knowledge_base()
    ids = {doc.id for doc in docs}
    assert ids == EXPECTED_DOC_IDS


def test_each_doc_has_required_fields():
    docs = load_knowledge_base()
    for doc in docs:
        assert doc.title
        assert doc.url.startswith("http")
        assert doc.effective_date
        assert doc.content


def test_format_for_prompt_includes_all_doc_ids():
    text = format_knowledge_base_for_prompt()
    for doc_id in EXPECTED_DOC_IDS:
        assert doc_id in text


def _doc(doc_id: str, content: str) -> KnowledgeDoc:
    return KnowledgeDoc(id=doc_id, title=doc_id, url="https://x", effective_date="2026-01-01", content=content)


def test_select_relevant_docs_returns_all_when_under_limit():
    docs = [_doc("a", "biểu phí chuyển tiền"), _doc("b", "bảo trì hệ thống")]
    assert select_relevant_docs("nội dung bất kỳ", docs, limit=5) == docs


def test_select_relevant_docs_ranks_by_keyword_overlap():
    docs = [
        _doc("fee", "Ngân hàng thu phí chuyển tiền liên ngân hàng 11.000 đồng mỗi giao dịch"),
        _doc("maintenance", "Hệ thống Internet Banking bảo trì định kỳ hàng tháng"),
        _doc("unrelated", "Chương trình khuyến mãi thẻ tín dụng mùa hè"),
    ]
    post_content = "Tôi bị trừ phí chuyển tiền liên ngân hàng cao bất thường, mong ngân hàng giải thích"

    result = select_relevant_docs(post_content, docs, limit=1)

    assert result == [docs[0]]


def test_select_relevant_docs_falls_back_to_first_n_when_no_overlap():
    docs = [_doc(str(i), f"nội dung {i} hoàn toàn không liên quan") for i in range(5)]
    result = select_relevant_docs("từ khoá lạ hoắc xyz", docs, limit=2)
    assert len(result) == 2


def _default_test_db_url() -> str:
    base = get_settings().database_url
    root, sep, dbname = base.rpartition("/")
    return f"{root}/{dbname}_test" if sep else base


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", _default_test_db_url())


def _connectable_engine():
    try:
        engine = create_engine(TEST_DATABASE_URL)
        with engine.connect():
            pass
        return engine
    except Exception:
        return None


_engine = _connectable_engine()

# Chỉ áp dụng cho test DB-backed bên dưới — các test thuần (load_knowledge_base/select_relevant_docs
# ở trên) không cần Postgres nên KHÔNG được gắn skipif này (khác test_runner_persistence.py, nơi cả
# file đều cần DB).
requires_db = pytest.mark.skipif(
    _engine is None, reason="Không kết nối được Postgres — chạy `docker compose up -d db` để test"
)


@pytest.fixture
def _db_session():
    Base.metadata.create_all(_engine)
    session = sessionmaker(bind=_engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(_engine)


@requires_db
def test_load_topic_documents_scopes_by_topic(_db_session):
    session = _db_session
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x")
    session.add(user)
    session.flush()
    topic_a = Topic(user_id=user.id, name="A", status="active")
    topic_b = Topic(user_id=user.id, name="B", status="active")
    session.add_all([topic_a, topic_b])
    session.flush()

    session.add_all(
        [
            OfficialDocument(topic_id=topic_a.id, title="Tài liệu A", url="https://a.example/1", content="nội dung A"),
            OfficialDocument(topic_id=topic_b.id, title="Tài liệu B", url="https://b.example/1", content="nội dung B"),
        ]
    )
    session.commit()

    docs_a = load_topic_documents(session, topic_a.id)
    assert [d.title for d in docs_a] == ["Tài liệu A"]

    docs_b = load_topic_documents(session, topic_b.id)
    assert [d.title for d in docs_b] == ["Tài liệu B"]


@requires_db
def test_load_topic_documents_excludes_news_category(_db_session):
    """Bài báo (category='news', qua NewsApifyCollector) là tin BÊN THỨ BA — không được lọt vào
    knowledge base mà Verification Agent dùng để đối chiếu "văn bản CHÍNH THỨC" của ngân hàng."""
    session = _db_session
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x")
    session.add(user)
    session.flush()
    topic = Topic(user_id=user.id, name="A", status="active")
    session.add(topic)
    session.flush()

    session.add_all(
        [
            OfficialDocument(
                topic_id=topic.id, title="Thông báo chính thức", url="https://a.example/1",
                content="nội dung", category="notice",
            ),
            OfficialDocument(
                topic_id=topic.id, title="Bài báo bên thứ ba", url="https://news.example/1",
                content="nội dung", category="news",
            ),
        ]
    )
    session.commit()

    docs = load_topic_documents(session, topic.id)
    assert [d.title for d in docs] == ["Thông báo chính thức"]
