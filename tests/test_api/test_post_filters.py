"""Bộ lọc kết hợp trên GET /topics/{id}/posts: từ khoá, nguồn, mức độ nghiêm trọng, khoảng thời
gian, trạng thái case — tất cả chạy ở backend (query DB), kết hợp được (AND)."""

import os
import uuid
from datetime import UTC, datetime, timedelta

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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _owner_headers(api_client) -> tuple[dict, str]:
    """Trả về (headers, user_id) — cần cả 2 vì dataset() phải seed topic ĐÚNG dưới user_id này để
    get_accessible_topic của endpoint nhận ra chủ sở hữu khớp với token trong headers. Tạo User
    trực tiếp qua DB (tự đăng ký công khai đã gỡ, xem src/api/routes_auth.py) thay vì qua
    POST /auth/register."""
    email = f"{uuid.uuid4()}@example.com"
    session = sessionmaker(bind=_engine)()
    try:
        session.add(User(email=email, password_hash=hash_password("testpass123"), is_verified=True))
        session.commit()
    finally:
        session.close()
    r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    return headers, me.json()["id"]


@pytest_asyncio.fixture
async def dataset(api_client):
    """Đăng nhập 1 chủ sở hữu thật qua API, rồi dựng 1 topic có 2 nguồn, 4 post trải đủ các trục
    lọc, và 1 pain point có lifecycle_status cụ thể để kiểm tra join qua topic_label — TẤT CẢ dưới
    đúng user_id đó, để mọi request trong test (dùng cùng headers) truy cập được."""
    headers, owner_id = await _owner_headers(api_client)
    session = sessionmaker(bind=_engine)()
    try:
        topic = Topic(user_id=uuid.UUID(owner_id), name="Test Bank", status="active")
        session.add(topic)
        session.flush()
        gp = Source(topic_id=topic.id, type="google_play", config={})
        app_store = Source(topic_id=topic.id, type="app_store", config={})
        session.add_all([gp, app_store])
        session.flush()

        now = datetime.now(UTC)

        def _post(source, content, days_ago, severity, sentiment, topic_label=None):
            post = Post(
                topic_id=topic.id,
                source_id=source.id,
                external_id=str(uuid.uuid4()),
                content=content,
                language="vi",
                posted_at=now - timedelta(days=days_ago),
            )
            session.add(post)
            session.flush()
            if topic_label is not None:
                session.add(
                    Prediction(
                        post_id=post.id,
                        sentiment=sentiment,
                        topic_label=topic_label,
                        severity_score=severity,
                        confidence_score=0.9,
                        consensus_status="confirmed",
                    )
                )
            return post

        # Thuộc pain point "lỗi ứng dụng" (sẽ set lifecycle_status="in_progress" bên dưới).
        p_login_error = _post(gp, "app bị crash liên tục khi đăng nhập", 1, 0.9, "negative", "lỗi ứng dụng")
        # Cùng nhóm topic_label, severity thấp hơn, nguồn khác, ngày xa hơn.
        p_login_error_2 = _post(app_store, "ứng dụng hơi chậm", 10, 0.2, "neutral", "lỗi ứng dụng")
        # Không thuộc pain point nào (topic_label khác, không có PainPoint tương ứng).
        p_no_case = _post(gp, "phí dịch vụ hơi cao nhưng chấp nhận được", 2, 0.5, "neutral", "phí dịch vụ")
        # Chưa phân tích (không có Prediction) — kiểm tra không vỡ khi thiếu prediction.
        p_unanalyzed = _post(gp, "chưa rõ đánh giá thế nào", 1, 0.0, "neutral", None)

        pain_point = PainPoint(
            topic_id=topic.id, title="lỗi ứng dụng", post_count=2, severity_avg=0.55, lifecycle_status="in_progress"
        )
        session.add(pain_point)
        session.commit()

        return {
            "headers": headers,
            "topic_id": str(topic.id),
            "pain_point_id": str(pain_point.id),
            "p_login_error": str(p_login_error.id),
            "p_login_error_2": str(p_login_error_2.id),
            "p_no_case": str(p_no_case.id),
            "p_unanalyzed": str(p_unanalyzed.id),
        }
    finally:
        session.close()


@pytest.mark.asyncio
async def test_keyword_search_matches_content(api_client, dataset):
    headers = dataset["headers"]
    r = await api_client.get(f"/api/v1/topics/{dataset['topic_id']}/posts?q=crash", headers=headers)
    ids = {p["id"] for p in r.json()}
    assert ids == {dataset["p_login_error"]}


@pytest.mark.asyncio
async def test_source_type_filter(api_client, dataset):
    headers = dataset["headers"]
    r = await api_client.get(f"/api/v1/topics/{dataset['topic_id']}/posts?source_type=app_store", headers=headers)
    ids = {p["id"] for p in r.json()}
    assert ids == {dataset["p_login_error_2"]}


@pytest.mark.asyncio
async def test_severity_bucket_filter(api_client, dataset):
    headers = dataset["headers"]
    r = await api_client.get(f"/api/v1/topics/{dataset['topic_id']}/posts?severity=high", headers=headers)
    ids = {p["id"] for p in r.json()}
    assert ids == {dataset["p_login_error"]}  # severity 0.9

    r = await api_client.get(f"/api/v1/topics/{dataset['topic_id']}/posts?severity=low", headers=headers)
    ids = {p["id"] for p in r.json()}
    assert dataset["p_login_error_2"] in ids  # severity 0.2


@pytest.mark.asyncio
async def test_date_range_filter(api_client, dataset):
    headers = dataset["headers"]
    today = datetime.now(UTC).date().isoformat()
    # Chỉ lấy hôm nay -> loại post 10 ngày trước.
    r = await api_client.get(
        f"/api/v1/topics/{dataset['topic_id']}/posts?date_from={today}&date_to={today}", headers=headers
    )
    ids = {p["id"] for p in r.json()}
    assert dataset["p_login_error_2"] not in ids


@pytest.mark.asyncio
async def test_lifecycle_status_filter_only_matches_posts_in_that_pain_point(api_client, dataset):
    headers = dataset["headers"]
    r = await api_client.get(
        f"/api/v1/topics/{dataset['topic_id']}/posts?lifecycle_status=in_progress", headers=headers
    )
    ids = {p["id"] for p in r.json()}
    # Pain Point Agent CHỈ gom review sentiment=negative (xem src/analysis/pain_point.py) —
    # p_login_error_2 cùng topic_label "lỗi ứng dụng" nhưng sentiment=neutral nên KHÔNG thuộc case
    # này dù trùng nhóm chủ đề; xem được ở danh sách phản hồi đã phân tích chung, không phải ở đây.
    assert ids == {dataset["p_login_error"]}
    assert dataset["p_login_error_2"] not in ids
    # Post không thuộc pain point nào (topic_label khác / chưa phân tích) không khớp lọc này dù
    # có tồn tại trong topic.
    assert dataset["p_no_case"] not in ids
    assert dataset["p_unanalyzed"] not in ids


@pytest.mark.asyncio
async def test_pain_point_lifecycle_status_populated_in_response(api_client, dataset):
    headers = dataset["headers"]
    r = await api_client.get(f"/api/v1/topics/{dataset['topic_id']}/posts?q=crash", headers=headers)
    post = r.json()[0]
    assert post["pain_point_lifecycle_status"] == "in_progress"

    r = await api_client.get(f"/api/v1/topics/{dataset['topic_id']}/posts?q=phí", headers=headers)
    post = r.json()[0]
    assert post["pain_point_lifecycle_status"] is None

    # sentiment=neutral, dù cùng topic_label "lỗi ứng dụng" với 1 pain point đang in_progress —
    # không được gắn lifecycle_status của case đó (xem test phía trên).
    r = await api_client.get(f"/api/v1/topics/{dataset['topic_id']}/posts?q=chậm", headers=headers)
    post = r.json()[0]
    assert post["id"] == dataset["p_login_error_2"]
    assert post["pain_point_lifecycle_status"] is None


@pytest.mark.asyncio
async def test_pain_point_posts_drilldown_excludes_non_negative_sentiment(api_client, dataset):
    """GET /pain-points/{id}/posts là danh sách hiển thị TRONG trang chi tiết pain point — phải
    khớp đúng cách Pain Point Agent đếm post_count (chỉ sentiment=negative), không phải mọi post
    trùng topic_label. p_login_error_2 (neutral, cùng topic_label) không được lọt vào đây."""
    headers = dataset["headers"]
    r = await api_client.get(f"/api/v1/pain-points/{dataset['pain_point_id']}/posts", headers=headers)
    ids = {p["id"] for p in r.json()}
    assert ids == {dataset["p_login_error"]}
    assert dataset["p_login_error_2"] not in ids


@pytest.mark.asyncio
async def test_pain_point_posts_drilldown_filters_by_source_type(api_client, dataset):
    """Cho phép xem riêng phản hồi của từng nguồn ngay tại trang pain point (xem
    PainPointSummary.sources) — p_login_error thuộc google_play."""
    headers = dataset["headers"]
    r = await api_client.get(
        f"/api/v1/pain-points/{dataset['pain_point_id']}/posts?source_type=google_play", headers=headers
    )
    ids = {p["id"] for p in r.json()}
    assert ids == {dataset["p_login_error"]}

    r = await api_client.get(
        f"/api/v1/pain-points/{dataset['pain_point_id']}/posts?source_type=app_store", headers=headers
    )
    assert r.json() == []


@pytest.mark.asyncio
async def test_combined_filters_apply_as_and(api_client, dataset):
    headers = dataset["headers"]
    # source_type=google_play AND lifecycle_status=in_progress -> chỉ p_login_error (google_play),
    # p_login_error_2 bị loại vì nó ở app_store.
    r = await api_client.get(
        f"/api/v1/topics/{dataset['topic_id']}/posts?source_type=google_play&lifecycle_status=in_progress",
        headers=headers,
    )
    ids = {p["id"] for p in r.json()}
    assert ids == {dataset["p_login_error"]}


@pytest.mark.asyncio
async def test_keyword_search_escapes_wildcards(api_client, dataset):
    """Từ khoá chứa ký tự đại diện của ILIKE ('%', '_') không được hiểu nhầm thành mẫu tìm kiếm."""
    headers = dataset["headers"]
    r = await api_client.get(f"/api/v1/topics/{dataset['topic_id']}/posts?q=%", headers=headers)
    assert r.status_code == 200
    assert r.json() == []
