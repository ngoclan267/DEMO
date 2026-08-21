from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from src.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Trả về user id (chuỗi) nếu token hợp lệ, None nếu không (hết hạn/sai chữ ký/malformed)."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    return payload.get("sub")
