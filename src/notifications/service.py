import logging
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import get_settings
from src.db.models import Notification, PainPoint, Topic, TopicMember, User
from src.notifications.email import render_email, send_email

logger = logging.getLogger(__name__)

# Diễn giải tiếng Việt cho pain_points.reference_status — tránh để lộ giá trị enum thô ra email
# người dùng, và nói rõ đây là đối chiếu văn bản chứ không phải "đã xác minh khách hàng".
REFERENCE_STATUS_LABEL = {
    "matched": "có văn bản chính thức liên quan",
    "no_match": "không tìm thấy văn bản liên quan",
    "conflicting": "các nguồn mâu thuẫn, cần xem xét",
}


def _create_notification(
    session: Session,
    *,
    user_id: UUID,
    to_email: str,
    topic: Topic,
    pain_point: PainPoint | None,
    notification_type: str,
    message: str,
    subject: str,
) -> Notification:
    """Tạo bản ghi Notification + gửi email nếu kênh của topic có bật email. Dùng chung cho cả 4
    loại thông báo (cảnh báo vượt ngưỡng, được giao việc, đã xử lý xong, bản tin hàng ngày) để
    không lặp logic. pain_point=None cho bản tin hàng ngày — thông báo cấp topic, không gắn 1 case
    cụ thể."""
    notification = Notification(
        user_id=user_id,
        topic_id=topic.id,
        pain_point_id=pain_point.id if pain_point else None,
        channel=topic.notify_channel,
        notification_type=notification_type,
        severity=pain_point.severity_avg if pain_point else None,
        message=message,
    )
    session.add(notification)

    if topic.notify_channel in ("email", "both"):
        # pain_point=None (bản tin hàng ngày) -> dẫn về topic; có pain_point -> dẫn thẳng vào case
        # cụ thể, đỡ phải tự tìm trong danh sách.
        base_url = get_settings().frontend_base_url
        if pain_point is not None:
            cta_url = f"{base_url}/topics/{topic.id}/pain-points/{pain_point.id}"
            cta_label = "Xem pain point"
        else:
            cta_url = f"{base_url}/topics/{topic.id}"
            cta_label = "Xem chủ đề"
        send_email(
            to=to_email,
            subject=subject,
            html_body=render_email(heading=subject, body_html=f"<p>{message}</p>", cta_url=cta_url, cta_label=cta_label),
        )

    session.commit()
    return notification


def check_and_notify(session: Session, pain_point: PainPoint) -> Notification | None:
    """Sinh cảnh báo khi pain_point vượt ngưỡng cảnh báo (Topic.alert_threshold) của topic chứa
    nó. Sau lần báo đầu tiên (đạt alert_threshold), CHỈ báo tiếp khi post_count đạt gấp đôi mốc đã
    báo lần trước (`last_notified_post_count`) — vd threshold=10: báo ở 10, rồi im lặng tới 20 mới
    báo tiếp, rồi 40, 80... Trước đây báo lại ở MỌI post_count mới (post_count > last_notified),
    tức là cứ có thêm 1 review là báo thêm 1 lần cho case đang tăng nhanh — quá nhiều thông báo dồn
    dập, gây rối mắt và làm loãng những cảnh báo thực sự đáng chú ý.
    Tôn trọng `Topic.notify_enabled` (tắt thông báo cho topic nhưng vẫn giữ dữ liệu pain point)
    và `Topic.notify_channel` (email/web/both theo lựa chọn người dùng).
    """
    topic = pain_point.topic

    if not topic.notify_enabled:
        return None
    if pain_point.post_count < topic.alert_threshold:
        return None
    if pain_point.last_notified_post_count is not None and pain_point.post_count < pain_point.last_notified_post_count * 2:
        return None

    message = (
        f'Pain point "{pain_point.title}" trong topic "{topic.name}" đã đạt {pain_point.post_count} '
        f"phản hồi (ngưỡng cảnh báo: {topic.alert_threshold}). Đối chiếu văn bản chính thức: "
        f"{REFERENCE_STATUS_LABEL.get(pain_point.reference_status, pain_point.reference_status)}."
    )

    notification = _create_notification(
        session,
        user_id=topic.user_id,
        to_email=topic.user.email,
        topic=topic,
        pain_point=pain_point,
        notification_type="threshold_alert",
        message=message,
        subject=f"Cảnh báo pain point: {pain_point.title} ({topic.name})",
    )
    pain_point.last_notified_post_count = pain_point.post_count
    session.commit()

    logger.info("Đã tạo notification cho pain_point=%s (topic=%s)", pain_point.title, topic.name)
    return notification


def notify_assignment(session: Session, pain_point: PainPoint, actor_user_id: UUID) -> Notification | None:
    """Báo cho người VỪA được giao pain point này — để họ biết cần xử lý gì. Không tự báo nếu
    người thực hiện thao tác giao việc chính là người được giao (tự giao cho mình thì đã biết rồi,
    không cần thông báo)."""
    assignee = pain_point.assigned_user
    if assignee is None or assignee.id == actor_user_id:
        return None

    topic = pain_point.topic
    message = (
        f'Bạn vừa được giao xử lý pain point "{pain_point.title}" trong chủ đề "{topic.name}" '
        f"({pain_point.post_count} phản hồi liên quan)."
    )
    notification = _create_notification(
        session,
        user_id=assignee.id,
        to_email=assignee.email,
        topic=topic,
        pain_point=pain_point,
        notification_type="assigned",
        message=message,
        subject=f"Bạn được giao xử lý: {pain_point.title} ({topic.name})",
    )
    logger.info("Đã báo giao việc pain_point=%s cho user=%s", pain_point.title, assignee.id)
    return notification


def notify_department_assignment(session: Session, pain_point: PainPoint, department: str) -> list[Notification]:
    """Báo cho TOÀN BỘ nhân viên thuộc `department` trong chủ đề này khi hệ thống TỰ ĐỘNG gán pain
    point cho phòng ban đó (xem src/analysis/department_routing.py::auto_route_pain_point) — khác
    notify_assignment() ở trên (báo 1 assigned_user_id cụ thể): tự động phân việc theo phòng ban
    KHÔNG chọn người cụ thể, gán cả `department`, để bất kỳ ai trong phòng xử lý trước tự nhận qua
    LifecyclePanel (PATCH .../lifecycle) như hiện có."""
    topic = pain_point.topic
    members = (
        session.query(User)
        .join(TopicMember, TopicMember.user_id == User.id)
        .filter(TopicMember.topic_id == topic.id, TopicMember.department == department)
        .all()
    )
    if not members:
        return []

    message = (
        f'Pain point "{pain_point.title}" trong chủ đề "{topic.name}" vừa được hệ thống tự động gán '
        f'cho phòng ban "{department}" ({pain_point.post_count} phản hồi liên quan) — ai xử lý '
        f"trước có thể tự nhận."
    )
    notifications = [
        _create_notification(
            session,
            user_id=member.id,
            to_email=member.email,
            topic=topic,
            pain_point=pain_point,
            notification_type="department_assigned",
            message=message,
            subject=f'Pain point mới cho phòng "{department}": {pain_point.title} ({topic.name})',
        )
        for member in members
    ]
    logger.info(
        "Đã báo phân việc phòng ban '%s' cho %d nhân viên, pain_point=%s", department, len(members), pain_point.title
    )
    return notifications


def notify_contact_request(session: Session, admins: list[User], company_name: str, contact_name: str) -> list[Notification]:
    """Báo TOÀN BỘ platform admin có yêu cầu liên hệ mới ngay TRONG hệ thống (chuông thông báo) —
    tách riêng khỏi việc gửi email cho admin (routes_contact.py tự gửi email riêng, mẫu khác hẳn),
    để admin thấy được ngay cả khi chưa/không check email. topic_id/pain_point_id=None vì yêu cầu
    liên hệ không gắn với topic nào — doanh nghiệp gửi form này CHƯA có tài khoản/chủ đề. Không đi
    qua _create_notification() (yêu cầu 1 Topic cụ thể để build CTA link/đọc notify_channel) — tạo
    thẳng Notification, không tự gửi email (đã có luồng email riêng ở nơi gọi)."""
    notifications = [
        Notification(
            user_id=admin.id,
            topic_id=None,
            pain_point_id=None,
            channel="web",
            notification_type="contact_request",
            message=f'Doanh nghiệp "{company_name}" ({contact_name}) vừa gửi yêu cầu liên hệ tư vấn.',
        )
        for admin in admins
    ]
    session.add_all(notifications)
    session.commit()
    return notifications


def notify_resolution(session: Session, pain_point: PainPoint, actor_user_id: UUID) -> Notification | None:
    """Báo cho người phụ trách khi pain point họ đang xử lý được đánh dấu đã xong — để họ biết mà
    chuyển sang việc khác. Không tự báo nếu chính người phụ trách là người đánh dấu resolved."""
    assignee = pain_point.assigned_user
    if assignee is None or assignee.id == actor_user_id:
        return None

    topic = pain_point.topic
    message = f'Pain point "{pain_point.title}" trong chủ đề "{topic.name}" mà bạn phụ trách đã được xử lý xong.'
    notification = _create_notification(
        session,
        user_id=assignee.id,
        to_email=assignee.email,
        topic=topic,
        pain_point=pain_point,
        notification_type="resolved",
        message=message,
        subject=f"Đã xử lý xong: {pain_point.title} ({topic.name})",
    )
    logger.info("Đã báo hoàn thành pain_point=%s cho user=%s", pain_point.title, assignee.id)
    return notification
