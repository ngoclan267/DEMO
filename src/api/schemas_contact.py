from pydantic import BaseModel, EmailStr, Field


class ContactRequest(BaseModel):
    """Form "Liên hệ tư vấn" công khai trên trang giới thiệu — thay cho tự đăng ký đã gỡ (xem
    routes_contact.py). Không tạo tài khoản/chủ đề nào ở đây, chỉ gửi email cho platform admin."""

    company_name: str = Field(min_length=1, max_length=255)
    contact_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    message: str | None = Field(default=None, max_length=2000)
