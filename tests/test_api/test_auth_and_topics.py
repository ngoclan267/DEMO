"""API-level test cho auth (đăng nhập, kiểm soát truy cập theo chủ sở hữu) + PII redaction. Cần
Postgres test thật, ghi đè `get_db` để trỏ vào DB test riêng (không phải DB dev — tránh tạo user/
topic rác trong dữ liệu thật).

Tự đăng ký công khai + tự tạo chủ đề đã gỡ (xem src/api/routes_auth.py, src/api/routes_topics.py —
tài khoản/chủ đề giờ luôn do platform admin/chủ sở hữu chủ đề tạo hộ) — các test ở đây seed User/
Topic trực tiếp qua DB thay vì đi qua 2 endpoint đã gỡ."""

import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.security import hash_password
from src.config import get_settings
from src.db.models import Base, PainPoint, Post, Prediction, Source, Topic, User
from src.db.session import get_db
from src.main import app


def _default_test_db_url() -> str:
    base = get_settings().database_url
    root, sep, dbname = base.rpartition("/")
    if not sep:
        return base
    return f"{root}/{dbname}_test"


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

pytestmark = pytest.mark.skipif(
    _engine is None, reason="Không kết nối được Postgres — chạy `docker compose up -d db` để test API"
)


@pytest.fixture(scope="module", autouse=True)
def _setup_tables():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture(autouse=True)
def _override_get_db():
    session_factory = sessionmaker(bind=_engine)

    def _get_test_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _new_user_headers(api_client, *, username: str | None = None, password: str = "testpass123") -> tuple[dict, str]:
    """Tạo User trực tiếp qua DB (is_verified=True) rồi đăng nhập — tự đăng ký công khai đã gỡ, xem
    module docstring. Trả về (headers, user_id)."""
    email = f"{uuid.uuid4()}@example.com"
    session = sessionmaker(bind=_engine)()
    try:
        user = User(email=email, username=username, password_hash=hash_password(password), is_verified=True)
        session.add(user)
        session.commit()
        user_id = str(user.id)
    finally:
        session.close()
    r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, user_id


def _new_topic(user_id: str, name: str = "Test Topic") -> str:
    """Tạo Topic trực tiếp qua DB, gán cho user_id — tự tạo chủ đề (POST /topics tự phục vụ) đã gỡ,
    chỉ platform admin tạo được chủ đề qua POST /topics/admin."""
    session = sessionmaker(bind=_engine)()
    try:
        topic = Topic(user_id=uuid.UUID(user_id), name=name)
        session.add(topic)
        session.commit()
        return str(topic.id)
    finally:
        session.close()


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(api_client):
    _, user_id = await _new_user_headers(api_client)
    session = sessionmaker(bind=_engine)()
    try:
        email = session.get(User, uuid.UUID(user_id)).email
    finally:
        session.close()
    r = await api_client.post("/api/v1/auth/login", json={"email": email, "password": "wrongpass"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_by_username_is_case_insensitive():
    """Đăng nhập bằng identifier khác hoa/thường (vd "ANHTUAN") vẫn khớp đúng username đã lưu (xem
    _find_user_by_identifier trong routes_auth.py, tự hạ chữ thường input trước khi so khớp).
    Username LƯU LUÔN ở dạng chữ thường (bất biến trước đây do RegisterRequest.normalize_username
    đảm bảo lúc tự đăng ký — endpoint đó đã gỡ, username giờ chỉ còn gán được qua seed DB trực tiếp,
    nơi gọi phải TỰ đảm bảo bất biến này)."""
    suffix = uuid.uuid4().hex[:10]
    username = f"anh{suffix}"
    email = f"{uuid.uuid4()}@example.com"
    session = sessionmaker(bind=_engine)()
    try:
        session.add(User(email=email, username=username, password_hash=hash_password("testpass123"), is_verified=True))
        session.commit()
    finally:
        session.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as api_client:
        r = await api_client.post(
            "/api/v1/auth/login", json={"identifier": f"ANH{suffix}", "password": "testpass123"}
        )
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_topics_are_isolated_per_user(api_client):
    _, user_a_id = await _new_user_headers(api_client)
    headers_b, _ = await _new_user_headers(api_client)
    topic_id = _new_topic(user_a_id, "A's topic")

    r = await api_client.get(f"/api/v1/topics/{topic_id}", headers=headers_b)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(api_client):
    r = await api_client.get("/api/v1/topics")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_pain_point_drill_down_and_detail_exclude_raw_content(api_client):
    """PII: raw_content (chứa tên người đánh giá gốc từ Google Play/App Store) không bao giờ
    được trả về qua bất kỳ endpoint nào, kể cả drill-down và post detail."""
    headers, user_id = await _new_user_headers(api_client)
    topic_id = _new_topic(user_id, "PII Test Topic")

    secret_reviewer_name = "NguyenVanBiMat123"
    session_factory = sessionmaker(bind=_engine)
    db = session_factory()
    try:
        source = Source(topic_id=uuid.UUID(topic_id), type="google_play", config={"package_name": "x"})
        db.add(source)
        db.flush()
        post = Post(
            topic_id=uuid.UUID(topic_id),
            source_id=source.id,
            external_id="ext-1",
            raw_content=f'{{"userName": "{secret_reviewer_name}", "content": "app loi"}}',
            content="app loi",
            language="vi",
        )
        db.add(post)
        db.flush()
        db.add(
            Prediction(
                post_id=post.id,
                sentiment="negative",
                topic_label="lỗi ứng dụng",
                severity_score=0.8,
                confidence_score=0.9,
                verification_status="unverified",
                content_reliability="high",
                reference_status="no_match",
                consensus_status="confirmed",
            )
        )
        db.add(PainPoint(topic_id=uuid.UUID(topic_id), title="lỗi ứng dụng", post_count=1, reference_status="no_match"))
        db.commit()
        post_id = str(post.id)
        pain_point_id = str(db.query(PainPoint).filter_by(topic_id=uuid.UUID(topic_id)).first().id)
    finally:
        db.close()

    r = await api_client.get(f"/api/v1/pain-points/{pain_point_id}/posts", headers=headers)
    assert r.status_code == 200
    assert secret_reviewer_name not in r.text
    assert "raw_content" not in r.text

    r = await api_client.get(f"/api/v1/posts/{post_id}", headers=headers)
    assert r.status_code == 200
    assert secret_reviewer_name not in r.text
    assert "raw_content" not in r.text
