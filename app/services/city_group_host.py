"""城市大群群主：任命、资料、轻治理（删消息 / 禁言）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_message import ActivityMessage
from app.models.city_group_host import CityGroupHost, CityGroupHostAction, CityGroupMute
from app.models.user import User
from app.services.city_hall import CITY_HALL_ACTIVITY_KIND, is_city_hall_activity, normalize_city_code
from app.services.city_hall_region_catalog import load_static_prefecture_blocks
from app.services.content_moderation import assert_text_content_safe
from app.services.wechat_content_security import SCENE_SOCIAL

HOST_STATUS_ACTIVE = "active"
HOST_STATUS_SUSPENDED = "suspended"
HOST_STATUS_RESIGNED = "resigned"
HOST_ROLE_OWNER = "owner"
HOST_ROLE_DEPUTY = "deputy"
MAX_DEPUTIES = 2
ANNOUNCEMENT_WEEKLY_LIMIT = 3
MUTE_HOURS = 24
MUTE_TARGET_WEEKLY_LIMIT = 1


def _uid_str(uid: int) -> str:
    return f"u_{uid}"


def parse_public_user_id(user_id: str) -> int:
    s = (user_id or "").strip()
    if s.startswith("u_"):
        s = s[2:]
    if not s.isdigit():
        raise ValueError("invalid user id")
    return int(s)


def parse_message_id(message_id: str) -> int:
    s = (message_id or "").strip()
    if s.startswith("msg_"):
        s = s[4:]
    if not s.isdigit():
        raise ValueError("invalid message id")
    return int(s)


def _city_name_from_catalog(city_code: str) -> str:
    cc = (city_code or "").strip()
    for blk in load_static_prefecture_blocks():
        for c in blk["cities"]:
            if c["cityCode"] == cc:
                return c["cityName"]
    return cc


def host_badge_label(city_code: str, role: str) -> str:
    name = _city_name_from_catalog(city_code)
    if role == HOST_ROLE_OWNER:
        return f"{name}群主"
    return f"{name}副群主"


async def get_city_hall_by_code(db: AsyncSession, city_code: str) -> Activity | None:
    cc = normalize_city_code(city_code)
    return await db.scalar(
        select(Activity).where(
            Activity.activity_kind == CITY_HALL_ACTIVITY_KIND,
            Activity.city_hall_city_code == cc,
        )
    )


async def get_active_hosts(db: AsyncSession, city_code: str) -> list[tuple[CityGroupHost, User]]:
    cc = normalize_city_code(city_code)
    rows = await db.execute(
        select(CityGroupHost, User)
        .join(User, User.id == CityGroupHost.user_id)
        .where(
            CityGroupHost.city_code == cc,
            CityGroupHost.status == HOST_STATUS_ACTIVE,
        )
        .order_by(
            CityGroupHost.role.asc(),
            CityGroupHost.appointed_at.asc(),
        )
    )
    return list(rows.all())


async def get_owner_host(db: AsyncSession, city_code: str) -> CityGroupHost | None:
    cc = normalize_city_code(city_code)
    return await db.scalar(
        select(CityGroupHost).where(
            CityGroupHost.city_code == cc,
            CityGroupHost.role == HOST_ROLE_OWNER,
            CityGroupHost.status == HOST_STATUS_ACTIVE,
        )
    )


async def build_host_role_map(db: AsyncSession, city_code: str) -> dict[int, str]:
    hosts = await get_active_hosts(db, city_code)
    return {u.id: h.role for h, u in hosts}


async def get_host_record_for_user(
    db: AsyncSession, city_code: str, user_id: int
) -> CityGroupHost | None:
    cc = normalize_city_code(city_code)
    return await db.scalar(
        select(CityGroupHost).where(
            CityGroupHost.city_code == cc,
            CityGroupHost.user_id == user_id,
            CityGroupHost.status == HOST_STATUS_ACTIVE,
        )
    )


async def assert_active_host(db: AsyncSession, city_code: str, user_id: int) -> CityGroupHost:
    host = await get_host_record_for_user(db, city_code, user_id)
    if not host:
        raise HTTPException(status_code=403, detail="Not a city group host")
    return host


async def list_city_host_badges(db: AsyncSession, user_id: int) -> list[dict]:
    rows = await db.execute(
        select(CityGroupHost).where(
            CityGroupHost.user_id == user_id,
            CityGroupHost.status == HOST_STATUS_ACTIVE,
        )
    )
    out: list[dict] = []
    for h in rows.scalars().all():
        out.append(
            {
                "cityCode": h.city_code,
                "cityName": _city_name_from_catalog(h.city_code),
                "role": h.role,
                "badgeLabel": host_badge_label(h.city_code, h.role),
            }
        )
    return out


async def host_summary_from_row(host: CityGroupHost, user: User) -> dict:
    return {
        "userId": _uid_str(user.id),
        "nickname": user.nickname,
        "avatarUrl": user.avatar_url,
        "role": host.role,
        "badgeLabel": host_badge_label(host.city_code, host.role),
    }


async def build_city_group_profile(
    db: AsyncSession,
    city_code: str,
    *,
    member_count: int = 0,
    display_name: str = "",
    activity_id: str | None = None,
    current_user_id: int | None = None,
) -> dict:
    cc = normalize_city_code(city_code)
    hosts = await get_active_hosts(db, cc)
    owner_row = next(((h, u) for h, u in hosts if h.role == HOST_ROLE_OWNER), None)
    deputies = [(h, u) for h, u in hosts if h.role == HOST_ROLE_DEPUTY]

    owner = None
    announcement = None
    welcome_text = None
    if owner_row:
        oh, ou = owner_row
        owner = await host_summary_from_row(oh, ou)
        announcement = oh.announcement
        welcome_text = oh.welcome_text

    current_role = None
    if current_user_id:
        for h, _ in hosts:
            if h.user_id == current_user_id:
                current_role = h.role
                break

    return {
        "cityCode": cc,
        "displayName": display_name,
        "memberCount": member_count,
        "activityId": activity_id,
        "owner": owner,
        "deputies": [await host_summary_from_row(h, u) for h, u in deputies],
        "announcement": announcement,
        "welcomeText": welcome_text,
        "currentUserHostRole": current_role,
    }


async def _log_action(
    db: AsyncSession,
    *,
    host: CityGroupHost,
    actor_user_id: int,
    action: str,
    target_message_id: int | None = None,
    target_user_id: int | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        CityGroupHostAction(
            host_id=host.id,
            city_code=host.city_code,
            actor_user_id=actor_user_id,
            action=action,
            target_message_id=target_message_id,
            target_user_id=target_user_id,
            detail=detail,
        )
    )


async def _count_recent_actions(
    db: AsyncSession,
    host_id: int,
    action: str,
    *,
    days: int = 7,
    target_user_id: int | None = None,
) -> int:
    since = datetime.now(UTC) - timedelta(days=days)
    filters = [
        CityGroupHostAction.host_id == host_id,
        CityGroupHostAction.action == action,
        CityGroupHostAction.created_at >= since,
    ]
    if target_user_id is not None:
        filters.append(CityGroupHostAction.target_user_id == target_user_id)
    return int(
        await db.scalar(select(func.count(CityGroupHostAction.id)).where(*filters)) or 0
    )


async def admin_appoint_host(
    db: AsyncSession,
    *,
    city_code: str,
    user_id: int,
    role: str,
    appointed_by: int | None,
) -> CityGroupHost:
    cc = normalize_city_code(city_code)
    if role not in (HOST_ROLE_OWNER, HOST_ROLE_DEPUTY):
        raise HTTPException(status_code=400, detail="invalid role")

    user = await db.scalar(select(User).where(User.id == user_id))
    if not user or user.status != "active":
        raise HTTPException(status_code=404, detail="User not found")

    existing_same = await db.scalar(
        select(CityGroupHost).where(
            CityGroupHost.city_code == cc,
            CityGroupHost.user_id == user_id,
            CityGroupHost.status == HOST_STATUS_ACTIVE,
        )
    )
    if existing_same:
        raise HTTPException(status_code=409, detail="User is already a host for this city")

    if role == HOST_ROLE_OWNER:
        current_owner = await get_owner_host(db, cc)
        if current_owner:
            current_owner.status = HOST_STATUS_RESIGNED
            current_owner.resigned_at = datetime.now(UTC)
    else:
        dep_count = await db.scalar(
            select(func.count(CityGroupHost.id)).where(
                CityGroupHost.city_code == cc,
                CityGroupHost.role == HOST_ROLE_DEPUTY,
                CityGroupHost.status == HOST_STATUS_ACTIVE,
            )
        )
        if int(dep_count or 0) >= MAX_DEPUTIES:
            raise HTTPException(status_code=409, detail="Deputy limit reached")

    host = CityGroupHost(
        city_code=cc,
        user_id=user_id,
        role=role,
        status=HOST_STATUS_ACTIVE,
        appointed_by=appointed_by,
    )
    db.add(host)
    await db.flush()
    return host


async def admin_update_host_status(
    db: AsyncSession,
    host_id: int,
    status: str,
) -> CityGroupHost:
    if status not in (HOST_STATUS_ACTIVE, HOST_STATUS_SUSPENDED, HOST_STATUS_RESIGNED):
        raise HTTPException(status_code=400, detail="invalid status")
    host = await db.scalar(select(CityGroupHost).where(CityGroupHost.id == host_id))
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    host.status = status
    if status in (HOST_STATUS_SUSPENDED, HOST_STATUS_RESIGNED):
        host.resigned_at = datetime.now(UTC)
    await db.flush()
    return host


async def patch_host_profile(
    db: AsyncSession,
    user: User,
    *,
    city_code: str,
    welcome_text: str | None = None,
    announcement: str | None = None,
    clear_welcome: bool = False,
    clear_announcement: bool = False,
) -> CityGroupHost:
    host = await assert_active_host(db, city_code, user.id)
    owner = host
    if host.role == HOST_ROLE_DEPUTY:
        owner = await get_owner_host(db, city_code)
        if not owner:
            raise HTTPException(status_code=500, detail="City owner missing")

    if welcome_text is not None:
        text = welcome_text.strip()
        if text:
            await assert_text_content_safe(user, text, scene=SCENE_SOCIAL)
        owner.welcome_text = text or None
    elif clear_welcome:
        owner.welcome_text = None

    if announcement is not None:
        text = announcement.strip()
        if text:
            await assert_text_content_safe(user, text, scene=SCENE_SOCIAL)
            recent = await _count_recent_actions(db, host.id, "announcement_update")
            if recent >= ANNOUNCEMENT_WEEKLY_LIMIT:
                raise HTTPException(status_code=429, detail="Announcement update limit reached")
        owner.announcement = text or None
        owner.announcement_updated_at = datetime.now(UTC)
        await _log_action(db, host=host, actor_user_id=user.id, action="announcement_update")
    elif clear_announcement:
        owner.announcement = None
        owner.announcement_updated_at = None

    await db.flush()
    return owner


async def host_delete_message(
    db: AsyncSession,
    user: User,
    *,
    city_code: str,
    message_id: str,
) -> None:
    host = await assert_active_host(db, city_code, user.id)
    msg_pk = parse_message_id(message_id)
    activity = await get_city_hall_by_code(db, city_code)
    if not activity:
        raise HTTPException(status_code=404, detail="City hall not found")

    msg = await db.scalar(
        select(ActivityMessage).where(
            ActivityMessage.id == msg_pk,
            ActivityMessage.activity_id == activity.id,
            ActivityMessage.deleted_at.is_(None),
        )
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    msg.deleted_at = datetime.now(UTC)
    await _log_action(
        db,
        host=host,
        actor_user_id=user.id,
        action="delete_message",
        target_message_id=msg.id,
    )
    await db.flush()


async def host_mute_member(
    db: AsyncSession,
    user: User,
    *,
    city_code: str,
    target_user_id: str,
) -> datetime:
    host = await assert_active_host(db, city_code, user.id)
    try:
        target_pk = parse_public_user_id(target_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid user id") from exc

    if target_pk == user.id:
        raise HTTPException(status_code=400, detail="Cannot mute yourself")

    target = await db.scalar(select(User).where(User.id == target_pk))
    if not target or target.status != "active":
        raise HTTPException(status_code=404, detail="User not found")

    if await get_host_record_for_user(db, city_code, target_pk):
        raise HTTPException(status_code=400, detail="Cannot mute a host")

    recent = await _count_recent_actions(
        db, host.id, "mute_member", target_user_id=target_pk
    )
    if recent >= MUTE_TARGET_WEEKLY_LIMIT:
        raise HTTPException(status_code=429, detail="Mute limit for this user reached")

    until = datetime.now(UTC) + timedelta(hours=MUTE_HOURS)
    db.add(
        CityGroupMute(
            city_code=normalize_city_code(city_code),
            user_id=target_pk,
            muted_by_host_id=host.id,
            muted_until=until,
        )
    )
    await _log_action(
        db,
        host=host,
        actor_user_id=user.id,
        action="mute_member",
        target_user_id=target_pk,
        detail=f"until={until.isoformat()}",
    )
    await db.flush()
    return until


async def is_user_muted_in_city(
    db: AsyncSession, city_code: str, user_id: int
) -> bool:
    cc = normalize_city_code(city_code)
    now = datetime.now(UTC)
    row = await db.scalar(
        select(CityGroupMute)
        .where(
            CityGroupMute.city_code == cc,
            CityGroupMute.user_id == user_id,
            CityGroupMute.muted_until > now,
        )
        .order_by(CityGroupMute.muted_until.desc())
        .limit(1)
    )
    return row is not None


async def city_code_for_activity(db: AsyncSession, activity: Activity) -> str | None:
    if not is_city_hall_activity(activity):
        return None
    return (activity.city_hall_city_code or activity.city_code or "").strip() or None
