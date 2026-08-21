import logging

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

_BRAND_NAME = "VigiBank"
_INK = "#221f1a"
_MUTED = "#8a8578"
_CREAM = "#f5f3ee"
_LINE = "#e5e1d8"
_HEADER_BG = "#1f2937"
_ACCENT = "#2563eb"


def render_email(heading: str, body_html: str, cta_url: str | None = None, cta_label: str | None = None) -> str:
    """Bọc nội dung vào layout chuyên nghiệp dùng chung cho MỌI email hệ thống gửi đi (xác thực,
    đặt mật khẩu, thông báo pain point, bản tin hàng ngày) — trước đây mỗi nơi tự viết
    f"<p>{message}</p>" thô, không có bố cục/thương hiệu, đọc trên điện thoại như tin nhắn lỗi.

    Style INLINE (không dùng <style> trong <head>) — nhiều email client di động (đặc biệt Gmail
    app) lược bỏ <style> ở <head>, chỉ style inline mới chắc chắn hiển thị đúng trên điện thoại.
    `cta_url`/`cta_label`: nút hành động chính (vd "Xác thực tài khoản", "Xem pain point") — kèm
    link thô bên dưới làm phương án dự phòng khi client chặn nút/không render link trong nút."""
    cta_html = ""
    if cta_url and cta_label:
        cta_html = f"""
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:22px;">
          <tr>
            <td style="border-radius:10px; background-color:{_ACCENT};">
              <a href="{cta_url}" style="display:inline-block; padding:12px 26px; font-size:14px; font-weight:600; color:#ffffff; text-decoration:none;">{cta_label}</a>
            </td>
          </tr>
        </table>
        <p style="margin:14px 0 0; font-size:11.5px; color:{_MUTED};">
          Hoặc dán link sau vào trình duyệt: <a href="{cta_url}" style="color:{_MUTED};">{cta_url}</a>
        </p>
        """
    return f"""<!doctype html>
<html>
  <body style="margin:0; padding:0; background-color:{_CREAM}; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_CREAM}; padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px; background-color:#ffffff; border-radius:16px; overflow:hidden; border:1px solid {_LINE};">
            <tr>
              <td style="background-color:{_HEADER_BG}; padding:18px 28px;">
                <span style="color:#ffffff; font-size:15px; font-weight:700; letter-spacing:0.03em;">{_BRAND_NAME}</span>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;">
                <h1 style="margin:0 0 14px; font-size:17px; line-height:1.4; color:{_INK};">{heading}</h1>
                <div style="font-size:14px; line-height:1.65; color:{_INK};">{body_html}</div>
                {cta_html}
              </td>
            </tr>
            <tr>
              <td style="padding:16px 28px; background-color:{_CREAM}; border-top:1px solid {_LINE};">
                <p style="margin:0; font-size:11px; color:{_MUTED};">Email tự động từ {_BRAND_NAME} — hệ thống theo dõi &amp; phân tích phản hồi khách hàng. Vui lòng không trả lời email này.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Gửi email qua Brevo HTTP API. Trả về True nếu gửi thành công, False nếu bỏ qua/lỗi.

    Dùng HTTP API (không phải SMTP) vì Railway (nơi deploy backend) chặn toàn bộ traffic SMTP ra
    ngoài (port 25/465/587) ở tầng hạ tầng — mọi kết nối smtplib.SMTP(...) đều lỗi
    "OSError: Network is unreachable" dù cấu hình đúng, xác nhận thật trên log production
    (2026-08-19). Brevo (như hầu hết dịch vụ email giao dịch) chỉ cần HTTPS, không bị chặn.

    Không raise exception — thiếu cấu hình hoặc lỗi mạng không nên làm sập luồng nghiệp vụ gọi hàm
    này (forgot-password, notification service); log lại để biết email không gửi được.
    """
    settings = get_settings()
    if not settings.brevo_api_key or not settings.brevo_sender_email:
        logger.warning("Chưa cấu hình BREVO_API_KEY/BREVO_SENDER_EMAIL — bỏ qua gửi email tới %s: %s", to, subject)
        return False

    try:
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": settings.brevo_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "sender": {"email": settings.brevo_sender_email, "name": _BRAND_NAME},
                "to": [{"email": to}],
                "subject": subject,
                "htmlContent": html_body,
            },
            timeout=15,
        )
        response.raise_for_status()
        logger.info("Đã gửi email tới %s: %s", to, subject)
        return True
    except Exception:
        logger.exception("Lỗi khi gửi email tới %s", to)
        return False
