"""RFC 3339 UTC with Z suffix for JSON.

MySQL 常存「无时区 naive」时间。本项目按国内部署习惯，**naive 视为 Asia/Shanghai（北京/中国时间）**，
再统一转为 UTC 输出。若误把 naive 当 UTC 打 Z，东八区客户端会再 +8h，出现「实际 18:20 却显示 02:20」等问题。
已带 tzinfo 的 aware datetime 则先转 UTC 再序列化。
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

_SHANGHAI = ZoneInfo("Asia/Shanghai")


def datetime_to_rfc3339_utc_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_SHANGHAI)
    dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")
