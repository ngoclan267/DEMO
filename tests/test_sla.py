from datetime import UTC, datetime, timedelta

import pytest

from src.sla import compute_due_at, is_breached, severity_bucket

BASE = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.0, "low"),
        (0.33, "low"),
        (0.34, "medium"),  # đúng ngưỡng -> bậc trên
        (0.5, "medium"),
        (0.66, "medium"),
        (0.67, "high"),  # đúng ngưỡng -> bậc trên
        (1.0, "high"),
        (None, "low"),  # chưa có severity thì không đặt hạn gấp
    ],
)
def test_severity_bucket(score, expected):
    assert severity_bucket(score) == expected


@pytest.mark.parametrize(
    ("severity", "hours"),
    [(0.9, 24), (0.5, 72), (0.1, 168)],
)
def test_due_at_matches_business_rule(severity, hours):
    """Nghiêm trọng 24h, trung bình 72h, nhẹ 7 ngày."""
    assert compute_due_at(BASE, severity) == BASE + timedelta(hours=hours)


def test_open_case_past_due_is_breached():
    due = BASE
    assert is_breached("new", due, BASE + timedelta(seconds=1)) is True
    assert is_breached("in_progress", due, BASE + timedelta(days=3)) is True


def test_open_case_before_due_is_not_breached():
    assert is_breached("new", BASE + timedelta(hours=1), BASE) is False


@pytest.mark.parametrize("status", ["resolved", "duplicate", "ignored"])
def test_closed_case_never_breached(status):
    """Case đã đóng không tính quá hạn, kể cả khi đóng muộn — nếu không mọi case cũ sẽ đỏ vĩnh
    viễn và làm nhiễu chỉ số đang cần theo dõi."""
    assert is_breached(status, BASE, BASE + timedelta(days=30)) is False


def test_missing_due_at_is_not_breached():
    assert is_breached("new", None, BASE) is False
