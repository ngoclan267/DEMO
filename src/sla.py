"""Ngưỡng mức độ nghiêm trọng và hạn xử lý (SLA) — NGUỒN DUY NHẤT cho cả backend.

Trước đây ngưỡng severity bị chép ở 2 nơi (src/api/routes_dashboard.py và frontend Badges.tsx),
dễ lệch nhau khi sửa. Mọi chỗ cần phân bậc severity hoặc tính hạn xử lý đều phải dùng module này.
"""

from datetime import datetime, timedelta

SEVERITY_LOW_MAX = 0.34
SEVERITY_MEDIUM_MAX = 0.67

# Khoảng điểm [thấp, cao) cho từng bậc — dùng để LỌC theo bậc (WHERE score >= lo AND score < hi),
# khác với severity_bucket() vốn dùng để PHÂN LOẠI 1 điểm cụ thể. Cùng ngưỡng, chỉ khác chiều dùng.
SEVERITY_RANGES: dict[str, tuple[float, float]] = {
    "low": (0.0, SEVERITY_LOW_MAX),
    "medium": (SEVERITY_LOW_MAX, SEVERITY_MEDIUM_MAX),
    "high": (SEVERITY_MEDIUM_MAX, 1.0000001),  # +epsilon để điểm 1.0 (tối đa) vẫn khớp bậc "high"
}

# Hạn xử lý theo bậc nghiêm trọng, tính bằng giờ (yêu cầu nghiệp vụ: nghiêm trọng 24h,
# trung bình 72h, nhẹ 7 ngày).
SLA_HOURS: dict[str, int] = {"high": 24, "medium": 72, "low": 168}

# Các trạng thái vòng đời được coi là ĐÃ XONG — không còn đếm ngược SLA, không tính quá hạn.
CLOSED_LIFECYCLE_STATUSES = frozenset({"resolved", "duplicate", "ignored"})


def severity_bucket(score: float | None) -> str:
    """Quy điểm severity (0.0-1.0) về 3 bậc. None -> 'low' để không vô tình đặt hạn gấp cho case
    chưa có dữ liệu severity."""
    if score is None:
        return "low"
    if score < SEVERITY_LOW_MAX:
        return "low"
    if score < SEVERITY_MEDIUM_MAX:
        return "medium"
    return "high"


def compute_due_at(created_at: datetime, severity_avg: float | None) -> datetime:
    """Hạn xử lý = thời điểm phát hiện pain point + số giờ SLA của bậc nghiêm trọng."""
    return created_at + timedelta(hours=SLA_HOURS[severity_bucket(severity_avg)])


def is_breached(lifecycle_status: str, due_at: datetime | None, now: datetime) -> bool:
    """Quá hạn khi đã qua `due_at` mà case vẫn đang mở. Case đã đóng (resolved/duplicate/ignored)
    không bao giờ tính là quá hạn, kể cả khi đóng muộn — nếu không thì mọi case cũ sẽ đỏ vĩnh viễn
    và làm nhiễu chỉ số đang cần theo dõi."""
    if due_at is None or lifecycle_status in CLOSED_LIFECYCLE_STATUSES:
        return False
    return now > due_at
