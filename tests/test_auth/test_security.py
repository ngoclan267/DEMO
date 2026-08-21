from datetime import UTC, datetime, timedelta

from jose import jwt

from src.auth.security import create_access_token, decode_access_token, hash_password, verify_password
from src.config import get_settings


def test_hash_password_and_verify_roundtrip():
    hashed = hash_password("my-secret-password")
    assert hashed != "my-secret-password"
    assert verify_password("my-secret-password", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("my-secret-password")
    assert verify_password("wrong-password", hashed) is False


def test_access_token_roundtrip():
    token = create_access_token(subject="user-123")
    assert decode_access_token(token) == "user-123"


def test_decode_rejects_tampered_token():
    token = create_access_token(subject="user-123")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert decode_access_token(tampered) is None


def test_decode_rejects_expired_token():
    settings = get_settings()
    expired_payload = {"sub": "user-123", "exp": datetime.now(UTC) - timedelta(minutes=1)}
    expired_token = jwt.encode(expired_payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    assert decode_access_token(expired_token) is None


def test_decode_rejects_garbage_token():
    assert decode_access_token("not-a-real-token") is None
