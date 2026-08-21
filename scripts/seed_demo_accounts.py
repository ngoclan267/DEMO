#!/usr/bin/env python3
"""Tạo 2 tài khoản demo (đăng nhập được thật, dùng cho nút "Dùng thử ngay" ở trang đăng nhập) và
chuyển quyền sở hữu 2 topic sạch, nhiều dữ liệu thật sang 2 tài khoản này — mỗi ngân hàng 1 tài
khoản làm việc riêng, đúng khái niệm topic = workspace của 1 ngân hàng.

2 topic "SHB Saha Mobile Banking"/"TPBank Mobile" hiện thuộc user demo@ai20k.local (tạo bởi
scripts/seed_data.py từ trước khi có auth thật) — password_hash của user đó chỉ là placeholder
"seed-only-not-a-real-login", KHÔNG đăng nhập được. Script này không đụng gì tới demo@ai20k.local,
chỉ tạo user MỚI rồi chuyển topic sang, idempotent (chạy lại nhiều lần an toàn).

Usage:
  python scripts/seed_demo_accounts.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth.security import hash_password  # noqa: E402
from src.db.models import Topic, User  # noqa: E402
from src.db.session import SessionLocal  # noqa: E402

DEMO_PASSWORD = "Demo12345!"

# (email, họ tên, tên topic cần chuyển quyền sở hữu sang) — khớp đúng 2 chip demo ở trang đăng nhập
# (frontend/app/(auth)/login/page.tsx).
#
# Dùng TLD ".com" chứ không phải ".local": Pydantic EmailStr (email-validator) từ chối ".local" vì
# đây là special-use/reserved TLD theo IANA — GET /auth/me trả UserResponse (email: EmailStr) nên
# mọi lần serialize user có email .local đều crash 500 (ResponseValidationError), khiến
# refreshUser() ở frontend tưởng token hỏng và xoá luôn — bấm chip demo nào cũng bị văng ra.
DEMO_ACCOUNTS = [
    ("demo.shb@vigibank-demo.com", "SHB Saha (Demo)", "SHB Saha Mobile Banking"),
    ("demo.tpbank@vigibank-demo.com", "TPBank (Demo)", "TPBank Mobile"),
]

# Email cũ dùng TLD .local (tạo trước khi phát hiện lỗi EmailStr ở trên) — đổi tại chỗ sang email
# mới nếu tài khoản cũ còn tồn tại, để không tạo user trùng lặp mất token/lịch sử cũ.
LEGACY_EMAIL_RENAMES = {
    "demo.shb@vigibank.local": "demo.shb@vigibank-demo.com",
    "demo.tpbank@vigibank.local": "demo.tpbank@vigibank-demo.com",
}

# CỐ Ý không còn seed tài khoản quản trị demo (admin@vigibank-demo.com, mật khẩu cố định
# "Demo12345!") — từng bị lộ công khai ở trang đăng nhập kèm quyền is_platform_admin=True thật,
# một lỗ hổng bảo mật thật (bất kỳ ai cũng đăng nhập được với quyền quản trị TỔNG nền tảng). Quyền
# quản trị giờ chỉ cấp cho 1 tài khoản email thật duy nhất, tạo/xoá thủ công qua /admin/users
# (xem src/api/routes_admin.py), không seed tự động bằng mật khẩu cố định nữa.


def rename_legacy_email(session, old_email: str, new_email: str) -> None:
    old_user = session.query(User).filter_by(email=old_email).first()
    if old_user is None:
        return
    if session.query(User).filter_by(email=new_email).first() is not None:
        return
    old_user.email = new_email
    session.flush()
    print(f"Đã đổi email {old_email} -> {new_email}")


def get_or_create_user(session, email: str, full_name: str) -> User:
    user = session.query(User).filter_by(email=email).first()
    if user:
        return user
    user = User(
        email=email,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name=full_name,
        is_verified=True,
        username=None,
    )
    session.add(user)
    session.flush()
    return user


def main() -> None:
    session = SessionLocal()
    try:
        for old_email, new_email in LEGACY_EMAIL_RENAMES.items():
            rename_legacy_email(session, old_email, new_email)
        session.commit()

        for email, full_name, topic_name in DEMO_ACCOUNTS:
            user = get_or_create_user(session, email, full_name)

            topic = session.query(Topic).filter_by(name=topic_name).first()
            if topic is None:
                print(f"Bỏ qua: không tìm thấy topic '{topic_name}'")
                continue
            if topic.user_id != user.id:
                topic.user_id = user.id
                print(f"Đã chuyển quyền sở hữu topic '{topic_name}' sang {email}")
            else:
                print(f"Topic '{topic_name}' đã thuộc {email} từ trước")

        session.commit()
        print(f"\nSeed xong. Mật khẩu demo dùng chung: {DEMO_PASSWORD}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
