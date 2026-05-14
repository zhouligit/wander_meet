"""城市大群：以 ``activity_kind=city_hall`` 的虚拟活动承载，复用报名与活动消息。

- **系统管理员**：内置系统用户作为 ``organizer_id``（昵称「系统管理员」），不在群内占报名名额。
- **懒创建**：仅 ``get_or_create_city_hall_activity`` 会写库；``lookup`` 只读。首个用户通过 ``join``（或业务上先 ``get_or_create``）在无记录时创建群。
- **省内排序**：``city_hall_sort_key`` 默认使用 ``city_code`` 小写，便于与行政区划/车牌地区编号顺序一致。
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_phone
from app.models.activity import Activity
from app.models.user import User
from app.services.china_province_meta import infer_province_code

logger = logging.getLogger(__name__)

CITY_HALL_CATEGORY_ID = "__city_hall__"
CITY_HALL_ACTIVITY_KIND = "city_hall"
EVENT_ACTIVITY_KIND = "event"
SYSTEM_USER_PHONE_SEED = "_wm_internal_city_hall_system_v1"

_CITY_CODE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")


def normalize_city_code(raw: str) -> str:
    s = (raw or "").strip()
    if not s or not _CITY_CODE_PATTERN.fullmatch(s):
        raise ValueError("invalid cityCode")
    return s


def is_city_hall_activity(activity: Activity) -> bool:
    return activity.activity_kind == CITY_HALL_ACTIVITY_KIND


def city_hall_short_label(title: str) -> str:
    suf = " · 城市大群"
    if title.endswith(suf):
        return (title[: -len(suf)] or title).strip()
    return (title or "").strip() or title


def _city_hall_sort_key(city_code: str, city_label: str | None) -> str:
    """省内排序：优先展示名小写（便于首字母拉丁字），否则城市码小写（区划/车牌地区号序）。"""
    label = (city_label or "").strip()
    if label:
        base = label.lower()[:48]
        return f"{base}\t{city_code.lower()}"[:64]
    return city_code.lower()[:64]


async def ensure_city_hall_system_user(db: AsyncSession) -> int:
    ph = hash_phone(SYSTEM_USER_PHONE_SEED)
    u = await db.scalar(select(User).where(User.phone_hash == ph))
    if u:
        return u.id
    u = User(
        phone=None,
        phone_hash=ph,
        nickname="系统管理员",
        status="active",
        role="user",
    )
    db.add(u)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        u2 = await db.scalar(select(User).where(User.phone_hash == ph))
        if u2:
            return u2.id
        raise
    return u.id


async def get_or_create_city_hall_activity(
    db: AsyncSession,
    city_code: str,
    *,
    city_label: str | None = None,
    log_user_id: int | None = None,
) -> Activity:
    """表内已有该 ``city_hall_city_code`` 则直接返回；否则由系统账号创建（首个触发 ``join`` 的用户触发创建）。"""
    cc = normalize_city_code(city_code)
    existing = await db.scalar(
        select(Activity).where(
            Activity.activity_kind == CITY_HALL_ACTIVITY_KIND,
            Activity.city_hall_city_code == cc,
        )
    )
    if existing:
        return existing

    system_uid = await ensure_city_hall_system_user(db)
    display = (city_label or "").strip() or cc
    title = f"{display[:40]} · 城市大群"
    prov = infer_province_code(cc)
    sort_key = _city_hall_sort_key(cc, city_label)
    activity = Activity(
        organizer_id=system_uid,
        title=title[:80],
        description="同城交流群，请友善发言，遵守社区规范。",
        category_id=CITY_HALL_CATEGORY_ID,
        city_code=cc,
        city_hall_city_code=cc,
        city_hall_province_code=prov,
        city_hall_sort_key=sort_key,
        activity_kind=CITY_HALL_ACTIVITY_KIND,
        location_name="全城",
        address_detail=None,
        lat=0,
        lng=0,
        start_at=datetime.now(UTC),
        end_at=None,
        max_members=200_000,
        fee_type="free",
        fee_amount_cents=None,
        activity_status="published",
    )
    db.add(activity)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        existing2 = await db.scalar(
            select(Activity).where(
                Activity.activity_kind == CITY_HALL_ACTIVITY_KIND,
                Activity.city_hall_city_code == cc,
            )
        )
        if existing2:
            return existing2
        raise
    logger.info(
        "city_hall_created activity_id=%s city_code=%s user_id=%s",
        activity.id,
        cc,
        log_user_id,
    )
    return activity
