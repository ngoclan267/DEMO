import html
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.schemas_contact import ContactRequest
from src.db.models import ContactRequest as ContactRequestRecord
from src.db.models import User
from src.db.session import get_db
from src.notifications.email import render_email, send_email
from src.notifications.service import notify_contact_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contact", tags=["contact"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def submit_contact_request(payload: ContactRequest, db: Session = Depends(get_db)) -> None:
    """Form "Liên hệ tư vấn" công khai trên trang giới thiệu (thay cho tự đăng ký đã gỡ — xem
    src/api/routes_auth.py) — KHÔNG tạo tài khoản/chủ đề nào ở đây. LƯU DB TRƯỚC (bảng
    contact_requests, xem GET/PATCH /admin/contacts — trang /admin/contacts) rồi mới gửi email cho
    TOÀN BỘ platform admin — lưu DB độc lập với việc gửi email có admin nhận được hay không, tránh
    mất hẳn thông tin liên hệ nếu email bị rơi vào spam/chưa có admin nào lúc gửi. Admin xử lý xong
    thì tự tạo chủ đề + tài khoản chủ sở hữu cho doanh nghiệp qua POST /topics/admin (trang
    /admin)."""
    record = ContactRequestRecord(
        company_name=payload.company_name,
        contact_name=payload.contact_name,
        email=payload.email,
        phone=payload.phone,
        message=payload.message,
    )
    db.add(record)
    db.commit()

    admins = db.query(User).filter(User.is_platform_admin.is_(True)).all()
    if not admins:
        logger.warning("Có yêu cầu liên hệ mới nhưng chưa có tài khoản platform admin nào để gửi email")
        return None

    try:
        notify_contact_request(db, admins, payload.company_name, payload.contact_name)
    except Exception:
        # Thông báo trong hệ thống là BỔ SUNG cho email bên dưới — lỗi ở đây (vd DB tạm thời) không
        # được làm mất luôn cả email, request đã lưu contact_requests record thành công ở trên rồi.
        logger.exception("Lỗi khi tạo notification cho yêu cầu liên hệ mới — vẫn tiếp tục gửi email")
        db.rollback()

    # Endpoint công khai, không đăng nhập — mọi field text đều là input KHÔNG đáng tin, escape HTML
    # trước khi chèn vào email (render_email không tự escape phần body_html truyền vào).
    company_name = html.escape(payload.company_name)
    contact_name = html.escape(payload.contact_name)
    email = html.escape(payload.email)
    body_html = (
        f"<p><strong>Doanh nghiệp:</strong> {company_name}</p>"
        f"<p><strong>Người liên hệ:</strong> {contact_name}</p>"
        f"<p><strong>Email:</strong> {email}</p>"
    )
    if payload.phone:
        body_html += f"<p><strong>Điện thoại:</strong> {html.escape(payload.phone)}</p>"
    if payload.message:
        body_html += f"<p><strong>Lời nhắn:</strong> {html.escape(payload.message)}</p>"
    body_html += '<p style="margin-top:16px;"><em>Xem đầy đủ trong mục Quản trị → Yêu cầu liên hệ.</em></p>'

    for admin in admins:
        send_email(
            to=admin.email,
            subject=f"Yêu cầu tư vấn mới — {company_name}",
            html_body=render_email(heading="Yêu cầu tư vấn mới", body_html=body_html),
        )
    return None
