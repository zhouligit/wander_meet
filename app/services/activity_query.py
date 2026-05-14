"""Helpers for activity list filters (Beijing local dates, not-ended)."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import false, or_
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


def city_codes_for_place_filter(city_code: str) -> list[str]:
    """活动 ``city_code`` 可能与用户选的区县/地级市码不一致，扩展为候选集合再 ``IN`` 查询。"""
    s = (city_code or "").strip()
    if not s:
        return []
    if len(s) == 6 and s.isdigit():
        return list({s, s[:4] + "00", s[:2] + "0000"})
    return [s]


def activity_city_code_matches(column, city_code: str) -> ColumnElement[bool]:
    """按地点筛活动：``IN`` 省/市/区变体，并对省级、地级市码加前缀匹配（活动可能只存区县码）。"""
    s = (city_code or "").strip()
    if not s:
        return false()
    variants = city_codes_for_place_filter(s)
    parts: list[ColumnElement[bool]] = []
    if variants:
        parts.append(column.in_(variants))
    if len(s) == 6 and s.isdigit() and s[:2] != "00":
        if s.endswith("0000"):
            parts.append(column.startswith(s[:2]))
        elif s.endswith("00"):
            parts.append(column.startswith(s[:4]))
    if not parts:
        return false()
    return or_(*parts) if len(parts) > 1 else parts[0]


def effective_activity_status(activity, now_utc: datetime) -> str:
    """Compare using UTC-aware datetimes (MySQL/asyncmy may return naive from ORM)."""
    if activity.activity_status != "published":
        return activity.activity_status
    if activity.end_at is not None and to_utc(activity.end_at) <= now_utc:
        return "ended"
    return "published"
