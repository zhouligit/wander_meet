"""用户获客渠道 ``users.acquisition_source`` 规范化。

支持格式示例：
- ``mp_weixin`` / ``wx_share_friend`` — 渠道
- ``wx_share_friend:u_9`` — 好友分享 + 分享者 userId（统计）
- ``referral:ABC123`` — 邀请码裂变（绑定后写入，优先于分享渠道）
- ``share:u_9`` — 仅有分享者、无渠道时
"""

from __future__ import annotations

import re

_ACQ_PATTERN = re.compile(r"^[\w:\-\.]{1,64}$")
_SHARE_SHARER_PATTERN = re.compile(
    r"^(?P<channel>wx_share_(?:friend|timeline)|share):(?P<uid>u_\d+)$"
)


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


def parse_share_sharer_user_id(acquisition_source: str | None) -> int | None:
    """从 ``wx_share_*:u_{id}`` / ``share:u_{id}`` 解析分享者 user id。"""
    s = (acquisition_source or "").strip()
    m = _SHARE_SHARER_PATTERN.match(s)
    if not m:
        return None
    digits = m.group("uid")[2:]
    try:
        return int(digits)
    except ValueError:
        return None


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
