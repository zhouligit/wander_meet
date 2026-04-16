from datetime import UTC, datetime, timedelta
import hashlib

import jwt

from app.core.config import get_settings

settings = get_settings()

JWT_ALG = "HS256"
JWT_SECRET = f"{settings.app_name}-{settings.mysql_db}-secret"


def hash_phone(phone: str) -> str:
    return hashlib.sha256(phone.encode("utf-8")).hexdigest()


def create_access_token(user_id: int, expires_in_seconds: int = 7200) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])

