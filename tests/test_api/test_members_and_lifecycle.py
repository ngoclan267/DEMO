"""Thành viên chủ đề + vòng đời xử lý case.

Trọng tâm là KIỂM SOÁT TRUY CẬP: thành viên xem được dữ liệu nhưng không được quản trị chủ đề,
và không giao việc được cho người ngoài chủ đề.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.security import hash_password
from src.config import get_settings
from src.db.models import Base, PainPoint, Topic, User
from src.db.session import get_db
from src.main import app
from src.sla import compute_due_at


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


@pytest.fixture(autouse=True)
def _no_real_email():
    """SMTP thật đã cấu hình (Gmail) — không để mỗi lần thêm thành viên MỚI (tự tạo tài khoản, xem
    add_member trong routes_topics.py)/giao việc/resolved trong test gửi email thật. 3 nơi SỬ DỤNG
    send_email khác nhau nên phải patch cả 3, patch tại nơi dùng chứ không phải nơi định nghĩa."""
    with (
        patch("src.api.routes_auth.send_email"),
        patch("src.api.routes_topics.send_email"),
        patch("src.notifications.service.send_email"),
    ):
        yield


@pytest_asyncio.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _new_user(api_client) -> tuple[dict, str]:
    """Trả về (headers, email). Tạo User trực tiếp qua DB (is_verified=True) — tự đăng ký công khai
    đã gỡ (xem src/api/routes_auth.py), tài khoản giờ luôn do platform admin/chủ sở hữu chủ đề tạo
    hộ; các test trong file này không nhắm vào kiểm thử luồng tạo tài khoản, chỉ cần 1 tài khoản
    đăng nhập được (xem tests/test_api/test_email_verification.py cho luồng xác thực email thật)."""
    email = f"{uuid.uuid4()}@example.com"
    session = sessionmaker(bind=_engine)()
    try:
        session.add(User(email=email, password_hash=hash_password("testpass123"), is_verified=True))
        session.commit()
    finally:
        session.close()
    r = await api_client.post("/api/v1/auth/login", json={"identifier": email, "password": "testpass123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


async def _new_topic(api_client, headers) -> str:
    """Tạo Topic trực tiếp qua DB, gán cho đúng user đang đăng nhập ở `headers` — POST /topics tự
    phục vụ đã gỡ (chỉ platform admin tạo được chủ đề, qua POST /topics/admin); test ở đây không
    cần dựng cả luồng platform-admin chỉ để có 1 topic thuộc về user test."""
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    session = sessionmaker(bind=_engine)()
    try:
        topic = Topic(user_id=uuid.UUID(me.json()["id"]), name="Chủ đề test")
        session.add(topic)
        session.commit()
        return str(topic.id)
    finally:
        session.close()


def _seed_pain_point(topic_id: str, severity: float = 0.9) -> str:
    session = sessionmaker(bind=_engine)()
    try:
        pp = PainPoint(
            topic_id=uuid.UUID(topic_id), title="lỗi ứng dụng", post_count=12, severity_avg=severity
        )
        session.add(pp)
        session.commit()
        return str(pp.id)
    finally:
        session.close()


def _get_pain_point_row(pain_point_id: str) -> PainPoint:
    session = sessionmaker(bind=_engine)()
    try:
        return session.query(PainPoint).filter(PainPoint.id == uuid.UUID(pain_point_id)).one()
    finally:
        session.close()


def _force_due_at_override(pain_point_id: str, due_at: datetime) -> None:
    """Đặt due_at_overridden=True trực tiếp qua DB — dùng để dựng sẵn trạng thái 'đã được quản lý
    tuỳ chỉnh hạn' cho test kiểm tra endpoint KHÔNG được vô tình đụng vào (test bẫy thiết kế)."""
    session = sessionmaker(bind=_engine)()
    try:
        pp = session.query(PainPoint).filter(PainPoint.id == uuid.UUID(pain_point_id)).one()
        pp.due_at = due_at
        pp.due_at_overridden = True
        session.commit()
    finally:
        session.close()


@pytest.mark.asyncio
async def test_member_can_view_but_cannot_delete_topic(api_client):
    owner, _ = await _new_user(api_client)
    member, member_email = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)

    # Trước khi mời: người ngoài không thấy gì
    assert (await api_client.get(f"/api/v1/topics/{topic_id}", headers=member)).status_code == 404

    r = await api_client.post(
        f"/api/v1/topics/{topic_id}/members", json={"email": member_email}, headers=owner
    )
    assert r.status_code == 201

    # Sau khi mời: xem được chủ đề và dashboard
    assert (await api_client.get(f"/api/v1/topics/{topic_id}", headers=member)).status_code == 200
    assert (await api_client.get(f"/api/v1/topics/{topic_id}/dashboard", headers=member)).status_code == 200

    # Nhưng KHÔNG được quản trị: xoá chủ đề và quản lý thành viên vẫn chỉ chủ sở hữu
    assert (await api_client.delete(f"/api/v1/topics/{topic_id}", headers=member)).status_code == 404
    assert (
        await api_client.post(
            f"/api/v1/topics/{topic_id}/members", json={"email": "x@example.com"}, headers=member
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_add_member_creates_account_when_email_not_found(api_client):
    """Từ khi admin ngân hàng tự tạo được tài khoản nhân viên (thay vì chỉ mời người ĐÃ có tài
    khoản), email chưa tồn tại không còn bị 404 — hệ thống tự tạo User mới rồi thêm làm thành viên
    (xem add_member trong routes_topics.py)."""
    owner, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    new_email = "nhanvienmoi@example.com"
    r = await api_client.post(f"/api/v1/topics/{topic_id}/members", json={"email": new_email}, headers=owner)
    assert r.status_code == 201
    assert r.json()["email"] == new_email

    session = sessionmaker(bind=_engine)()
    try:
        created = session.query(User).filter(User.email == new_email).one()
        # Tài khoản nhân viên tự tạo: đã xác thực ngay, không phải đối tượng dùng thử/thanh toán —
        # không được dính cổng chặn hết-hạn-dùng-thử ở routes_auth.py::login().
        assert created.is_verified is True
        assert created.is_paid is True
        assert created.trial_ends_at is None
    finally:
        session.close()


@pytest.mark.asyncio
async def test_members_list_contains_owner_and_invited_only(api_client):
    owner, owner_email = await _new_user(api_client)
    member, member_email = await _new_user(api_client)
    _outsider, outsider_email = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    await api_client.post(f"/api/v1/topics/{topic_id}/members", json={"email": member_email}, headers=owner)

    r = await api_client.get(f"/api/v1/topics/{topic_id}/members", headers=member)
    assert r.status_code == 200
    emails = {m["email"] for m in r.json()}
    assert emails == {owner_email, member_email}
    assert outsider_email not in emails  # không lộ user không liên quan


@pytest.mark.asyncio
async def test_lifecycle_change_records_event_and_sets_resolved_at(api_client):
    owner, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    pain_point_id = _seed_pain_point(topic_id)

    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle",
        json={"lifecycle_status": "in_progress", "department": "Phòng CNTT", "note": "Đang điều tra"},
        headers=owner,
    )
    assert r.status_code == 200
    assert r.json()["lifecycle_status"] == "in_progress"
    assert r.json()["department"] == "Phòng CNTT"
    assert r.json()["resolved_at"] is None

    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"lifecycle_status": "resolved"}, headers=owner
    )
    assert r.json()["resolved_at"] is not None
    assert r.json()["is_breached"] is False  # case đã đóng không tính quá hạn

    r = await api_client.get(f"/api/v1/pain-points/{pain_point_id}/events", headers=owner)
    assert r.status_code == 200
    transitions = [(e["from_status"], e["to_status"]) for e in r.json()]
    assert ("in_progress", "resolved") in transitions
    assert ("new", "in_progress") in transitions


@pytest.mark.asyncio
async def test_cannot_assign_to_user_outside_topic(api_client):
    owner, _ = await _new_user(api_client)
    outsider, outsider_email = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    pain_point_id = _seed_pain_point(topic_id)

    me = (await api_client.get("/api/v1/auth/me", headers=outsider)).json()
    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"assigned_user_id": me["id"]}, headers=owner
    )
    assert r.status_code == 400

    # Sau khi mời vào chủ đề thì giao việc được
    await api_client.post(f"/api/v1/topics/{topic_id}/members", json={"email": outsider_email}, headers=owner)
    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"assigned_user_id": me["id"]}, headers=owner
    )
    assert r.status_code == 200
    assert r.json()["assigned_user"]["email"] == outsider_email


@pytest.mark.asyncio
async def test_duplicate_requires_valid_target(api_client):
    owner, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    pain_point_id = _seed_pain_point(topic_id)
    other_topic_id = await _new_topic(api_client, owner)
    foreign_pp_id = _seed_pain_point(other_topic_id)

    # Thiếu duplicate_of_id
    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"lifecycle_status": "duplicate"}, headers=owner
    )
    assert r.status_code == 400

    # Trỏ vào chính nó
    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle",
        json={"lifecycle_status": "duplicate", "duplicate_of_id": pain_point_id},
        headers=owner,
    )
    assert r.status_code == 400

    # Trỏ sang pain point của chủ đề khác
    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle",
        json={"lifecycle_status": "duplicate", "duplicate_of_id": foreign_pp_id},
        headers=owner,
    )
    assert r.status_code == 400

    # Hợp lệ: cùng chủ đề
    valid_target = _seed_pain_point(topic_id)
    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle",
        json={"lifecycle_status": "duplicate", "duplicate_of_id": valid_target},
        headers=owner,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_outsider_cannot_touch_pain_point_lifecycle(api_client):
    owner, _ = await _new_user(api_client)
    outsider, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    pain_point_id = _seed_pain_point(topic_id)

    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"lifecycle_status": "ignored"}, headers=outsider
    )
    assert r.status_code == 404
    assert (
        await api_client.get(f"/api/v1/pain-points/{pain_point_id}/events", headers=outsider)
    ).status_code == 404


@pytest.mark.asyncio
async def test_pain_points_filter_by_lifecycle_status(api_client):
    owner, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    kept = _seed_pain_point(topic_id)
    ignored = _seed_pain_point(topic_id)
    await api_client.patch(
        f"/api/v1/pain-points/{ignored}/lifecycle", json={"lifecycle_status": "ignored"}, headers=owner
    )

    r = await api_client.get(f"/api/v1/topics/{topic_id}/pain-points?lifecycle_status=new", headers=owner)
    ids = {pp["id"] for pp in r.json()}
    assert kept in ids
    assert ignored not in ids


@pytest.mark.asyncio
async def test_marking_pain_point_priority_persists_and_pins_it_first(api_client):
    owner, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    # severity thấp hơn hẳn "important" — nếu KHÔNG đánh dấu ưu tiên thì phải đứng SAU important
    # trong danh sách mặc định (sắp theo severity_avg, xem _pain_point_order_by).
    low_severity = _seed_pain_point(topic_id, severity=0.2)
    important = _seed_pain_point(topic_id, severity=0.9)

    r = await api_client.get(f"/api/v1/topics/{topic_id}/pain-points", headers=owner)
    ids_before = [pp["id"] for pp in r.json()]
    assert ids_before == [important, low_severity]  # mặc định: severity cao hơn đứng trước

    r = await api_client.patch(
        f"/api/v1/pain-points/{low_severity}/lifecycle", json={"is_priority": True}, headers=owner
    )
    assert r.status_code == 200
    assert r.json()["is_priority"] is True

    r = await api_client.get(f"/api/v1/topics/{topic_id}/pain-points", headers=owner)
    ids_after = [pp["id"] for pp in r.json()]
    # Đã đánh dấu ưu tiên -> đứng ĐẦU dù severity thấp hơn hẳn important (chưa đánh dấu).
    assert ids_after == [low_severity, important]

    r = await api_client.patch(
        f"/api/v1/pain-points/{low_severity}/lifecycle", json={"is_priority": False}, headers=owner
    )
    assert r.json()["is_priority"] is False
    r = await api_client.get(f"/api/v1/topics/{topic_id}/pain-points", headers=owner)
    assert [pp["id"] for pp in r.json()] == [important, low_severity]  # bỏ đánh dấu -> quay về mặc định


async def _notifications_of_type(api_client, headers, notification_type: str) -> list[dict]:
    r = await api_client.get("/api/v1/notifications?limit=100", headers=headers)
    return [n for n in r.json() if n["notification_type"] == notification_type]


@pytest.mark.asyncio
async def test_assignment_notifies_assignee_not_actor(api_client):
    owner, _ = await _new_user(api_client)
    member, member_email = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    await api_client.post(f"/api/v1/topics/{topic_id}/members", json={"email": member_email}, headers=owner)
    pain_point_id = _seed_pain_point(topic_id)

    me = (await api_client.get("/api/v1/auth/me", headers=member)).json()
    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"assigned_user_id": me["id"]}, headers=owner
    )
    assert r.status_code == 200

    assigned = await _notifications_of_type(api_client, member, "assigned")
    assert len(assigned) == 1
    assert assigned[0]["pain_point_id"] == pain_point_id
    assert assigned[0]["topic_id"] == topic_id

    # Chủ sở hữu (người thực hiện thao tác giao việc) không tự nhận thông báo về hành động của mình.
    owner_assigned = await _notifications_of_type(api_client, owner, "assigned")
    assert owner_assigned == []


@pytest.mark.asyncio
async def test_self_assignment_does_not_notify(api_client):
    owner, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    pain_point_id = _seed_pain_point(topic_id)
    me = (await api_client.get("/api/v1/auth/me", headers=owner)).json()

    await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"assigned_user_id": me["id"]}, headers=owner
    )
    assert await _notifications_of_type(api_client, owner, "assigned") == []


@pytest.mark.asyncio
async def test_reassigning_same_person_does_not_renotify(api_client):
    owner, _ = await _new_user(api_client)
    member, member_email = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    await api_client.post(f"/api/v1/topics/{topic_id}/members", json={"email": member_email}, headers=owner)
    pain_point_id = _seed_pain_point(topic_id)
    me = (await api_client.get("/api/v1/auth/me", headers=member)).json()

    for _ in range(2):
        await api_client.patch(
            f"/api/v1/pain-points/{pain_point_id}/lifecycle",
            json={"assigned_user_id": me["id"], "department": "Phòng CNTT"},
            headers=owner,
        )
    assert len(await _notifications_of_type(api_client, member, "assigned")) == 1


@pytest.mark.asyncio
async def test_resolution_notifies_assignee_not_resolver(api_client):
    owner, _ = await _new_user(api_client)
    member, member_email = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    await api_client.post(f"/api/v1/topics/{topic_id}/members", json={"email": member_email}, headers=owner)
    pain_point_id = _seed_pain_point(topic_id)
    me = (await api_client.get("/api/v1/auth/me", headers=member)).json()

    await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"assigned_user_id": me["id"]}, headers=owner
    )
    # Chủ sở hữu (không phải người phụ trách) đánh dấu resolved.
    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"lifecycle_status": "resolved"}, headers=owner
    )
    assert r.status_code == 200

    resolved = await _notifications_of_type(api_client, member, "resolved")
    assert len(resolved) == 1
    assert resolved[0]["pain_point_id"] == pain_point_id


@pytest.mark.asyncio
async def test_self_resolution_does_not_notify(api_client):
    """Người phụ trách tự đánh dấu case của mình đã xong thì không cần tự báo cho chính mình."""
    owner, _ = await _new_user(api_client)
    member, member_email = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    await api_client.post(f"/api/v1/topics/{topic_id}/members", json={"email": member_email}, headers=owner)
    pain_point_id = _seed_pain_point(topic_id)
    me = (await api_client.get("/api/v1/auth/me", headers=member)).json()

    await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"assigned_user_id": me["id"]}, headers=owner
    )
    await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"lifecycle_status": "resolved"}, headers=member
    )
    assert await _notifications_of_type(api_client, member, "resolved") == []


@pytest.mark.asyncio
async def test_unassigned_pain_point_resolved_creates_no_notification(api_client):
    owner, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    pain_point_id = _seed_pain_point(topic_id)

    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"lifecycle_status": "resolved"}, headers=owner
    )
    assert r.status_code == 200
    assert await _notifications_of_type(api_client, owner, "resolved") == []


@pytest.mark.asyncio
async def test_setting_due_at_override_persists_custom_deadline(api_client):
    owner, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    pain_point_id = _seed_pain_point(topic_id)
    custom_due_at = datetime.now(UTC) + timedelta(days=30)

    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle",
        json={"due_at_override": True, "due_at": custom_due_at.isoformat()},
        headers=owner,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["due_at_overridden"] is True
    assert datetime.fromisoformat(body["due_at"]) == custom_due_at


@pytest.mark.asyncio
async def test_due_at_override_true_without_due_at_returns_400(api_client):
    owner, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    pain_point_id = _seed_pain_point(topic_id)

    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"due_at_override": True}, headers=owner
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_clearing_due_at_override_recomputes_from_severity(api_client):
    owner, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    # severity 0.9 -> bậc "high" -> SLA 24h (xem src/sla.py).
    pain_point_id = _seed_pain_point(topic_id, severity=0.9)
    _force_due_at_override(pain_point_id, datetime.now(UTC) + timedelta(days=365))

    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"due_at_override": False}, headers=owner
    )
    assert r.status_code == 200
    body = r.json()
    assert body["due_at_overridden"] is False

    row = _get_pain_point_row(pain_point_id)
    expected_due_at = compute_due_at(row.created_at, row.severity_avg)
    assert abs((datetime.fromisoformat(body["due_at"]) - expected_due_at).total_seconds()) < 1


@pytest.mark.asyncio
async def test_unrelated_lifecycle_change_does_not_touch_due_at_override(api_client):
    """Test bẫy thiết kế: frontend gửi lại MỌI field mỗi lần lưu, kể cả lưu không liên quan (vd chỉ
    đổi phòng ban). Nếu endpoint suy luận override từ sự có mặt của due_at thay vì due_at_override
    tường minh, save không liên quan này sẽ vô tình đóng băng/xoá hạn tuỳ chỉnh đã đặt trước đó."""
    owner, _ = await _new_user(api_client)
    topic_id = await _new_topic(api_client, owner)
    pain_point_id = _seed_pain_point(topic_id)
    custom_due_at = datetime.now(UTC) + timedelta(days=30)
    _force_due_at_override(pain_point_id, custom_due_at)

    r = await api_client.patch(
        f"/api/v1/pain-points/{pain_point_id}/lifecycle", json={"department": "Phòng CNTT"}, headers=owner
    )
    assert r.status_code == 200
    body = r.json()
    assert body["due_at_overridden"] is True
    assert datetime.fromisoformat(body["due_at"]) == custom_due_at
