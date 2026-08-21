"""Bản tin tổng hợp hàng ngày — KHÔNG dùng LLM (tránh thêm 1 điểm phụ thuộc quota Gemini vào job
chạy mỗi ngày, trong khi quota free-tier đã nhiều lần là nút thắt thật của hệ thống trong quá
trình phát triển). Câu chữ dùng mẫu điền số liệu, giống cách 3 loại thông báo còn lại đang làm
(xem service.py)."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from src.db.models import Notification, Post, Prediction, Topic
from src.db.session import SessionLocal
from src.notifications.service import _create_notification

logger = logging.getLogger(__name__)

TOP_N = 3
SPIKE_RATIO_THRESHOLD = 0.5  # cảnh báo khi tăng > 50%
# Dưới 24h một chút — scheduler.py cho job này chạy NGAY khi container khởi động (bên cạnh mốc cron
# 7:00 hàng ngày), để bắt kịp trường hợp container bị restart trước khi kịp qua mốc 7:00 (đã quan
# sát thực tế: daily_digest CHƯA TỪNG được tạo dù threshold_alert vẫn hoạt động bình thường, vì môi
# trường dev restart scheduler thường xuyên nên container hiếm khi sống liên tục qua đúng mốc 7:00).
# Cooldown này tránh gửi trùng bản tin mỗi lần restart trong cùng một ngày.
DIGEST_COOLDOWN_HOURS = 20


def _window_stats(session: Session, topic_id, start: datetime, end: datetime) -> tuple[int, int]:
    """(tổng phản hồi ĐÃ PHÂN TÍCH, số tiêu cực) có Prediction.classified_at rơi trong [start, end)
    — nghĩa là AI HOÀN TẤT PHÂN TÍCH trong khung giờ này, KHÔNG phải post được đăng/thu thập trong
    khung giờ này.

    Lỗi THẬT đã xảy ra khi lọc theo effective_date (posted_at, fallback collected_at) như trước:
    quota LLM free-tier có hạn nên backlog chưa phân tích có thể rất lớn (xem DEFAULT_BATCH_LIMIT
    trong src/analysis/runner.py) — 1 post thu thập được TỪ NHIỀU NGÀY TRƯỚC nhưng chỉ vừa được AI
    phân tích XONG hôm nay sẽ bị lọc theo effective_date BỎ SÓT khỏi bản tin hôm nay (dù đúng là vừa
    phân tích xong hôm nay), khiến bản tin báo số phản hồi/tiêu cực THẤP HƠN NHIỀU so với thực tế đã
    phân tích trong ngày. Prediction.classified_at (thời điểm Classification Agent ghi kết quả, xem
    src/analysis/runner.py) mới đúng là "đã phân tích khi nào" — CHỈ đếm post ĐÃ CÓ Prediction (join
    thường, không phải outerjoin) nên classified_at luôn có giá trị, không cần coalesce/fallback."""
    total, negative = (
        session.query(
            func.count(Post.id),
            func.sum(case((Prediction.sentiment == "negative", 1), else_=0)),
        )
        .join(Prediction, Prediction.post_id == Post.id)
        .filter(Post.topic_id == topic_id, Prediction.classified_at >= start, Prediction.classified_at < end)
        .one()
    )
    return total or 0, negative or 0


def _new_counts_by_pain_point(session: Session, topic_id, start: datetime, end: datetime) -> dict[str, int]:
    """Số post PHÂN TÍCH XONG trong [start, end) (Prediction.classified_at, xem _window_stats) nhóm
    theo topic_label — 'đáng chú ý hôm nay' nghĩa là đang phát sinh nhiều trong ngày, KHÔNG phải
    post_count tổng dồn của PainPoint (1 case cũ đã ổn định vẫn có post_count cao nhưng không có gì
    mới). Dùng CÙNG mốc thời gian classified_at với _window_stats — Top 3/cảnh báo tăng đột biến bên
    dưới phải khớp cùng 1 định nghĩa "hôm nay" với tổng số ở đầu bản tin, không lệch nhau."""
    rows = (
        session.query(Prediction.topic_label, func.count(Post.id))
        .join(Post, Post.id == Prediction.post_id)
        .filter(
            Post.topic_id == topic_id,
            Prediction.topic_label.isnot(None),
            Prediction.classified_at >= start,
            Prediction.classified_at < end,
        )
        .group_by(Prediction.topic_label)
        .all()
    )
    return dict(rows)


def build_digest_message(session: Session, topic: Topic, now: datetime) -> str | None:
    """Trả về nội dung bản tin cho 1 topic, hoặc None nếu không có phản hồi ĐÃ PHÂN TÍCH nào trong
    24h qua (không đáng gửi bản tin rỗng) — xem _window_stats, số liệu CHỈ tính trên dữ liệu đã
    phân tích xong, không tính post còn nằm trong hàng đợi chờ."""
    last_24h_start = now - timedelta(hours=24)
    prior_24h_start = now - timedelta(hours=48)
    # Cùng khung giờ 24h nhưng lùi đúng 7 ngày — so sánh cùng "loại ngày trong tuần" để đỡ lệch
    # cuối tuần/ngày thường.
    week_ago_end = now - timedelta(days=7)
    week_ago_start = week_ago_end - timedelta(hours=24)

    total_24h, negative_24h = _window_stats(session, topic.id, last_24h_start, now)
    if total_24h == 0:
        return None

    total_week_ago, negative_week_ago = _window_stats(session, topic.id, week_ago_start, week_ago_end)

    rate_24h = negative_24h / total_24h * 100
    lines = [
        f'Bản tin ngày {now.strftime("%d/%m/%Y")} cho "{topic.name}": {total_24h} phản hồi đã phân tích, {rate_24h:.0f}% tiêu cực'
    ]
    if total_week_ago > 0:
        rate_week_ago = negative_week_ago / total_week_ago * 100
        diff = rate_24h - rate_week_ago
        if diff > 0:
            lines[0] += f" (tăng {diff:.0f} điểm % so với cùng khung giờ 7 ngày trước)"
        elif diff < 0:
            lines[0] += f" (giảm {abs(diff):.0f} điểm % so với cùng khung giờ 7 ngày trước)"
        else:
            lines[0] += " (không đổi so với cùng khung giờ 7 ngày trước)"
    else:
        lines[0] += " (7 ngày trước không có dữ liệu để so sánh)"

    counts_24h = _new_counts_by_pain_point(session, topic.id, last_24h_start, now)
    counts_prior_24h = _new_counts_by_pain_point(session, topic.id, prior_24h_start, last_24h_start)

    top3 = sorted(counts_24h.items(), key=lambda kv: kv[1], reverse=True)[:TOP_N]
    if top3:
        top_str = "; ".join(f'"{title}" ({count} mới)' for title, count in top3)
        lines.append(f"Top {len(top3)} pain point đáng chú ý hôm nay: {top_str}.")

    # Yêu cầu 24h trước phải > 0 để tránh chia 0 / báo "tăng vô hạn" cho case vừa mới xuất hiện —
    # case hoàn toàn mới đã nằm trong mục Top 3 ở trên rồi, không cần thêm cảnh báo trùng.
    spikes = []
    for title, count in counts_24h.items():
        prior = counts_prior_24h.get(title, 0)
        if prior > 0 and (count - prior) / prior > SPIKE_RATIO_THRESHOLD:
            pct = (count - prior) / prior * 100
            spikes.append(f'"{title}" tăng {pct:.0f}% ({prior} → {count} phản hồi/24h)')
    if spikes:
        lines.append("Cảnh báo tăng đột biến: " + "; ".join(spikes) + ".")

    return " ".join(lines)


def _digest_sent_recently(session: Session, topic_id, now: datetime) -> bool:
    cutoff = now - timedelta(hours=DIGEST_COOLDOWN_HOURS)
    return (
        session.query(Notification.id)
        .filter(
            Notification.topic_id == topic_id,
            Notification.notification_type == "daily_digest",
            Notification.sent_at >= cutoff,
        )
        .first()
        is not None
    )


def run_daily_digest(session: Session | None = None) -> int:
    """Sinh bản tin cho mọi topic active có notify_enabled — chạy 1 lần/ngày qua scheduler (cộng
    thêm 1 lần ngay lúc khởi động, xem DIGEST_COOLDOWN_HOURS ở trên). Trả về số bản tin đã tạo
    (dùng cho test + log)."""
    owns_session = session is None
    session = session or SessionLocal()
    now = datetime.now(UTC)
    created = 0
    try:
        topics = session.query(Topic).filter(Topic.status == "active", Topic.notify_enabled.is_(True)).all()
        for topic in topics:
            if _digest_sent_recently(session, topic.id, now):
                continue
            message = build_digest_message(session, topic, now)
            if message is None:
                continue
            _create_notification(
                session,
                user_id=topic.user_id,
                to_email=topic.user.email,
                topic=topic,
                pain_point=None,
                notification_type="daily_digest",
                message=message,
                subject=f"Bản tin hàng ngày: {topic.name}",
            )
            created += 1
            logger.info("Đã tạo bản tin hàng ngày cho topic=%s", topic.name)
    finally:
        if owns_session:
            session.close()
    return created
