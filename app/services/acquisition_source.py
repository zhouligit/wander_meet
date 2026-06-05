"""用户获客渠道 ``users.acquisition_source`` 规范化。"""

from __future__ import annotations

import re

_ACQ_PATTERN = re.compile(r"^[\w:\-\.]{1,64}$")


def normalize_acquisition_source(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s[:64]
    if not _ACQ_PATTERN.fullmatch(s):
        s = re.sub(r"[^\w:\-\.]", "_", s)[:64]
    return s or None


def resolve_new_user_acquisition_source(
    explicit: str | None,
    *,
    default: str | None,
) -> str | None:
    """新用户注册：优先客户端上报的 ``src``，否则平台默认值。"""
    normalized = normalize_acquisition_source(explicit)
    if normalized:
        return normalized
    return normalize_acquisition_source(default)
