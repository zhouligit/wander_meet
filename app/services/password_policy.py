"""密码强度与 bcrypt 哈希。"""

from __future__ import annotations

import re

import bcrypt

_BCRYPT_ROUNDS = 12


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "密码至少 8 位"
    if len(password) > 128:
        return "密码过长"
    if not re.search(r"[A-Za-z]", password):
        return "密码需包含字母"
    if not re.search(r"\d", password):
        return "密码需包含数字"
    return None


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
