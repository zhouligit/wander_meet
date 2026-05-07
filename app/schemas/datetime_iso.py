"""RFC 3339 UTC with Z suffix for JSON.

MySQL/asyncmy 常返回「无时区 naive」。不同字段语义不同：

- **活动开始/结束**：入库前经 ``to_utc()``，库里 naive 表示 **UTC 墙钟**，序列化时 naive 一律按 UTC。
- **聊天、私信、报名 joined_at 等**：多为 ``server_default=func.now()``，国内机房 naive 多为 **本地墙钟**，序列化用
  ``datetime_to_rfc3339_utc_z_shanghai_naive``。

已带 tzinfo 的 aware datetime 一律先 ``astimezone(UTC)`` 再输出。
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

_SHANGHAI = ZoneInfo("Asia/Shanghai")


def datetime_to_rfc3339_utc_z(dt: datetime | None) -> str | None:
    """Naive → interpret as UTC (activity ``start_at`` / ``end_at`` persistence)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def datetime_to_rfc3339_utc_z_shanghai_naive(dt: datetime | None) -> str | None:
    """Naive → interpret as Asia/Shanghai wall clock (typical MySQL NOW() on CST host)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_SHANGHAI)
    dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")
