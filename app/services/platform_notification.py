"""系统通知（平台侧）与私聊类通知的区分。"""

from __future__ import annotations

DM_NOTIFICATION_TYPES = frozenset({"dm_request", "dm_request_accepted"})


def is_platform_notification_type(notification_type: str | None) -> bool:
    return (notification_type or "").strip() not in DM_NOTIFICATION_TYPES
