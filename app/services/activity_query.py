"""Helpers for activity list filters (Beijing local dates, not-ended)."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, false, func, or_
from sqlalchemy.sql import ColumnElement

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment

HOME_ACTIVITY_WINDOW_DAYS = 7

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


def past_activity_condition(now_utc: datetime) -> ColumnElement[bool]:
    """已结束：``ended_at`` 已写、状态 ended/cancelled，或 published 且计划 ``end_at`` 已过。"""
    return or_(
        Activity.ended_at.isnot(None),
        Activity.activity_status.in_(("cancelled", "ended")),
        and_(
            Activity.activity_status == "published",
            Activity.end_at.isnot(None),
            Activity.end_at < now_utc,
        ),
    )


def my_activities_past_order():
    """历史活动按实际/计划结束时间倒序。"""
    return func.coalesce(Activity.ended_at, Activity.end_at, Activity.updated_at).desc()


def my_activities_upcoming_order():
    """未结束活动按开始时间正序（越近越靠上）。"""
    return Activity.start_at.asc()


def my_activities_event_desc_order():
    """普通活动按开始时间倒序（列表页「活动」区块）。"""
    return Activity.start_at.desc()


def my_activities_all_order(now_utc: datetime):
    """
    「全部」：未结束在前（开始时间正序），已结束在后（结束时间倒序）。
    """
    is_past = past_activity_condition(now_utc)
    past_key = func.coalesce(Activity.ended_at, Activity.end_at, Activity.updated_at)
    # 已结束：用负时间戳实现倒序；未结束：开始时间正序
    tie_break = case(
        (is_past, -func.unix_timestamp(past_key)),
        else_=func.unix_timestamp(Activity.start_at),
    )
    return [case((is_past, 1), else_=0).asc(), tie_break.asc()]


def upcoming_activity_condition(now_utc: datetime) -> ColumnElement[bool]:
    """进行中/未结束：published 且未到结束时间。"""
    return and_(
        Activity.activity_status == "published",
        not_ended_condition(now_utc),
    )


def beijing_day_range_utc(
    which: str, *, ref_utc: datetime | None = None
) -> tuple[datetime, datetime]:
    """Return [start, end) in UTC for calendar day in Asia/Shanghai."""
    ref = ref_utc or datetime.now(UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    local_today = ref.astimezone(TZ_BJ).date()
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


def next7d_window_bounds(now_utc: datetime | None = None) -> tuple[datetime, datetime]:
    """
    首页「近 7 天」：开始时间不早于北京时间今天 0 点，不晚于从现在起 7 天内。
    含今天已开始、尚未结束的活动（外层 ``not_ended_condition`` 负责未结束）。
    """
    now = now_utc or datetime.now(UTC)
    earliest, _ = beijing_day_range_utc("today", ref_utc=now)
    latest = now + timedelta(days=HOME_ACTIVITY_WINDOW_DAYS)
    return earliest, latest


def date_range_start_filters(
    date_range: str, *, now_utc: datetime | None = None
) -> list[ColumnElement[bool]]:
    if date_range in {"today", "tomorrow"}:
        start_utc, end_utc = beijing_day_range_utc(date_range, ref_utc=now_utc)
        return [Activity.start_at >= start_utc, Activity.start_at < end_utc]
    if date_range == "next7d":
        now = now_utc or datetime.now(UTC)
        earliest, _ = beijing_day_range_utc("today", ref_utc=now)
        latest = now + timedelta(days=HOME_ACTIVITY_WINDOW_DAYS)
        return [Activity.start_at >= earliest, Activity.start_at <= latest]
    return []


def enrollment_count_subquery():
    """已报名人数（joined），用于人气排序。"""
    return (
        select(func.count(ActivityEnrollment.id))
        .where(
            ActivityEnrollment.activity_id == Activity.id,
            ActivityEnrollment.status == "joined",
        )
        .correlate(Activity)
        .scalar_subquery()
    )


# 直辖市国标前两位：若用户选的是区县（如 110101），不应再并入 xx0000，否则 IN 到 110000 会扫进「整市」活动。
_MUNICIPALITY_PROVINCE_PREFIXES = frozenset({"11", "12", "31", "50"})


def city_codes_for_place_filter(city_code: str) -> list[str]:
    """活动 ``city_code`` 可能与用户选的区县/地级市码不一致，扩展为候选集合再 ``IN`` 查询。"""
    s = (city_code or "").strip()
    if not s:
        return []
    if len(s) == 6 and s.isdigit():
        variants: set[str] = {s, s[:4] + "00"}
        prov = s[:2] + "0000"
        skip_prov_bucket = s[:2] in _MUNICIPALITY_PROVINCE_PREFIXES and s != prov
        if not skip_prov_bucket:
            variants.add(prov)
        return list(variants)
    return [s]


def activity_city_code_matches(column, city_code: str) -> ColumnElement[bool]:
    """按地点筛活动：``IN`` 变体；省级用前两位前缀；**仅非直辖市**的地级市码（``xxxx00``）用前四位前缀。"""
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
        elif s.endswith("00") and s[:2] not in _MUNICIPALITY_PROVINCE_PREFIXES:
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
