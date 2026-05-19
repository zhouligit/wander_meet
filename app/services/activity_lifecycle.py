"""活动结束时间冗余字段维护。"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.activity import Activity


def mark_activity_ended(
    activity: Activity,
    now_utc: datetime | None = None,
    *,
    status: str | None = None,
) -> None:
    """写入 ``ended_at``（实际结束时刻），便于历史列表索引与排序。"""
    if now_utc is None:
        now_utc = datetime.now(UTC)
    if activity.ended_at is None:
        activity.ended_at = now_utc
    if status is not None:
        activity.activity_status = status
