"""邮箱规范化与格式校验（RFC 5322 简化）。"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9](?:[a-zA-Z0-9._%+-]{0,62}[a-zA-Z0-9])?"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def parse_email(text: str) -> str | None:
    s = (text or "").strip().lower()
    if not s or len(s) > 254:
        return None
    if ".." in s or s.startswith(".") or "@." in s:
        return None
    if not _EMAIL_RE.match(s):
        return None
    return s


def nickname_from_email(email: str) -> str:
    local = email.split("@", 1)[0]
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]", "", local)[:20]
    return cleaned or "旅人"


def mask_email(email: str) -> str:
    if "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        masked_local = "*"
    elif len(local) == 2:
        masked_local = f"{local[0]}*"
    else:
        masked_local = f"{local[0]}***{local[-1]}"
    return f"{masked_local}@{domain}"
