"""Helpers for activity list filters (Beijing local dates, not-ended)."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.sql import ColumnElement

from app.models.activity import Activity

TZ_BJ = ZoneInfo("Asia/Shanghai")


def to_utc(dt: datetime) -> datetime:
    """Normalize to UTC for persistence (MySQL/async drivers expect aware datetimes)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_utc_optional(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return to_utc(dt)


def not_ended_condition(now_utc: datetime) -> ColumnElement[bool]:
    return or_(Activity.end_at.is_(None), Activity.end_at >= now_utc)


def beijing_day_range_utc(which: str) -> tuple[datetime, datetime]:
    """Return [start, end) in UTC for calendar day in Asia/Shanghai."""
    local_today = datetime.now(TZ_BJ).date()
    if which == "tomorrow":
        d = local_today + timedelta(days=1)
    elif which == "today":
        d = local_today
    else:
        raise ValueError(which)
    day_start_local = datetime.combine(d, time.min, tzinfo=TZ_BJ)
    day_end_local = day_start_local + timedelta(days=1)
    return (
        day_start_local.astimezone(UTC),
        day_end_local.astimezone(UTC),
    )


def date_range_start_filters(date_range: str) -> list[ColumnElement[bool]]:
    if date_range not in {"today", "tomorrow"}:
        return []
    start_utc, end_utc = beijing_day_range_utc(date_range)
    return [Activity.start_at >= start_utc, Activity.start_at < end_utc]


def effective_activity_status(activity, now_utc: datetime) -> str:
    """Compare using UTC-aware datetimes (MySQL/asyncmy may return naive from ORM)."""
    if activity.activity_status != "published":
        return activity.activity_status
    if activity.end_at is not None and to_utc(activity.end_at) <= now_utc:
        return "ended"
    return "published"
