import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.auth.security import decode_access_token
from src.db.models import User
from src.db.session import get_db

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")

    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ hoặc đã hết hạn")

    try:
        user = db.get(User, uuid.UUID(user_id))
    except ValueError:
        user = None

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Người dùng không tồn tại")
    return user


def get_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    """Quản trị TỔNG nền tảng — khác chủ sở hữu topic (chỉ quản lý 1 workspace riêng). Dùng cho
    endpoint tạo topic thay doanh nghiệp khác (xem POST /topics/admin)."""
    if not current_user.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yêu cầu quyền quản trị nền tảng")
    return current_user
