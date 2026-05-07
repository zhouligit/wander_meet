from datetime import UTC, datetime, timedelta
import hashlib
from uuid import uuid4

import jwt

from app.core.config import get_settings

JWT_ALG = "HS256"


def _jwt_secret_key() -> str:
    s = get_settings()
    raw = (s.jwt_secret or "").strip()
    if raw:
        return raw
    return f"{s.app_name}-{s.mysql_db}-secret"


def hash_phone(phone: str) -> str:
    return hashlib.sha256(phone.encode("utf-8")).hexdigest()


def create_access_token(user_id: int, expires_in_seconds: int | None = None) -> str:
    settings = get_settings()
    ttl = (
        expires_in_seconds
        if expires_in_seconds is not None
        else settings.access_token_expires_seconds
    )
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "jti": uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret_key(), algorithm=JWT_ALG)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _jwt_secret_key(), algorithms=[JWT_ALG])

