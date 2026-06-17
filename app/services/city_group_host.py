"""城市大群群主：任命、资料、轻治理（删消息 / 禁言）。"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_message import ActivityMessage
from app.models.activity_enrollment import ActivityEnrollment
from app.models.city_group_host import CityGroupHost, CityGroupHostAction, CityGroupHostApplication, CityGroupMute
from app.models.growth_trust import UserTrustProfile
from app.models.user import User
from app.services.activity_query import activity_city_code_matches
from app.services.chat_unread import increment_chat_unread_for_message
from app.services.city_hall import CITY_HALL_ACTIVITY_KIND, EVENT_ACTIVITY_KIND, is_city_hall_activity, normalize_city_code
from app.services.city_hall_region_catalog import load_static_prefecture_blocks
from app.services.content_moderation import assert_text_content_safe
from app.services.wechat_content_security import SCENE_SOCIAL
from app.services.bos_storage import resolve_bos_read_url

HOST_STATUS_ACTIVE = "active"
HOST_STATUS_SUSPENDED = "suspended"
HOST_STATUS_RESIGNED = "resigned"
HOST_ROLE_OWNER = "owner"
HOST_ROLE_DEPUTY = "deputy"
MAX_DEPUTIES = 2
ANNOUNCEMENT_WEEKLY_LIMIT = 3
MUTE_HOURS = 24
MUTE_TARGET_WEEKLY_LIMIT = 1
APPLY_MIN_MEMBERS = 100
APPLY_VACANT_DAYS = 30
INACTIVE_OWNER_DAYS = 30
RECOMMEND_ACTIVITY_WEEKLY_LIMIT = 5
APP_TYPE_OWNER = "owner"
APP_TYPE_DEPUTY = "deputy"
APP_STATUS_PENDING = "pending"
APP_STATUS_APPROVED = "approved"
APP_STATUS_REJECTED = "rejected"


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


def _city_short_name_for_host_badge(city_name: str) -> str:
    name = (city_name or "").strip()
    short = re.sub(r"(特别行政区|自治州|地区|盟|市)$", "", name)
    return short or name


def host_badge_label(city_code: str, role: str) -> str:
    name = _city_short_name_for_host_badge(_city_name_from_catalog(city_code))
    if role == HOST_ROLE_OWNER:
        return f"{name}城主"
    return f"{name}副城主"


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
        "avatarUrl": resolve_bos_read_url(user.avatar_url),
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


async def enrich_profile_with_eligibility(
    db: AsyncSession,
    profile: dict,
    *,
    current_user_id: int | None,
) -> dict:
    elig = await get_host_application_eligibility(
        db,
        city_code=profile["cityCode"],
        member_count=int(profile.get("memberCount") or 0),
        user_id=current_user_id,
    )
    profile.update(elig)
    return profile


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
        last_active_at=datetime.now(UTC),
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
        if host.role == HOST_ROLE_OWNER:
            await promote_oldest_deputy_to_owner(db, host.city_code)
    await db.flush()
    return host


async def touch_host_active(db: AsyncSession, host: CityGroupHost) -> None:
    host.last_active_at = datetime.now(UTC)
    await db.flush()


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
            await assert_text_content_safe(user, text, scene=SCENE_SOCIAL, strict=True)
        owner.welcome_text = text or None
    elif clear_welcome:
        owner.welcome_text = None

    if announcement is not None:
        text = announcement.strip()
        if text:
            await assert_text_content_safe(user, text, scene=SCENE_SOCIAL, strict=True)
            recent = await _count_recent_actions(db, host.id, "announcement_update")
            if recent >= ANNOUNCEMENT_WEEKLY_LIMIT:
                raise HTTPException(status_code=429, detail="Announcement update limit reached")
        owner.announcement = text or None
        owner.announcement_updated_at = datetime.now(UTC)
        await _log_action(db, host=host, actor_user_id=user.id, action="announcement_update")
    elif clear_announcement:
        owner.announcement = None
        owner.announcement_updated_at = None

    await touch_host_active(db, host)
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
    await touch_host_active(db, host)
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
    await touch_host_active(db, host)
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


async def _user_photo_verified(db: AsyncSession, user_id: int) -> bool:
    tp = await db.scalar(select(UserTrustProfile).where(UserTrustProfile.user_id == user_id))
    return bool(tp and tp.photo_verified)


async def _user_joined_city_hall(db: AsyncSession, city_code: str, user_id: int) -> bool:
    activity = await get_city_hall_by_code(db, city_code)
    if not activity:
        return False
    en = await db.scalar(
        select(ActivityEnrollment).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.user_id == user_id,
            ActivityEnrollment.status == "joined",
        )
    )
    return en is not None


async def _owner_vacant_since(db: AsyncSession, city_code: str) -> datetime | None:
    cc = normalize_city_code(city_code)
    if await get_owner_host(db, cc):
        return None
    last_owner = await db.scalar(
        select(CityGroupHost)
        .where(
            CityGroupHost.city_code == cc,
            CityGroupHost.role == HOST_ROLE_OWNER,
            CityGroupHost.status.in_((HOST_STATUS_RESIGNED, HOST_STATUS_SUSPENDED)),
        )
        .order_by(CityGroupHost.resigned_at.desc(), CityGroupHost.id.desc())
        .limit(1)
    )
    if last_owner and last_owner.resigned_at:
        return last_owner.resigned_at
    activity = await get_city_hall_by_code(db, cc)
    if activity and activity.created_at:
        return activity.created_at
    return datetime.now(UTC)


async def get_host_application_eligibility(
    db: AsyncSession,
    *,
    city_code: str,
    member_count: int,
    user_id: int | None,
) -> dict:
    cc = normalize_city_code(city_code)
    owner = await get_owner_host(db, cc)
    pending_for_user = None
    can_apply = False
    deny_reason = None

    if owner:
        deny_reason = "has_owner"
    elif member_count < APPLY_MIN_MEMBERS:
        deny_reason = "member_count_low"
    else:
        vacant_since = await _owner_vacant_since(db, cc)
        if vacant_since:
            days = (datetime.now(UTC) - vacant_since.replace(tzinfo=UTC if vacant_since.tzinfo is None else vacant_since.tzinfo)).days
            if days < APPLY_VACANT_DAYS:
                deny_reason = "vacant_too_short"
            else:
                can_apply = True
        else:
            can_apply = True

    if user_id:
        pending = await db.scalar(
            select(CityGroupHostApplication).where(
                CityGroupHostApplication.city_code == cc,
                CityGroupHostApplication.user_id == user_id,
                CityGroupHostApplication.application_type == APP_TYPE_OWNER,
                CityGroupHostApplication.status == APP_STATUS_PENDING,
            )
        )
        if pending:
            pending_for_user = APP_STATUS_PENDING
            can_apply = False
            deny_reason = "pending_application"
        if can_apply:
            if not await _user_joined_city_hall(db, cc, user_id):
                can_apply = False
                deny_reason = "not_joined"
            elif not await _user_photo_verified(db, user_id):
                can_apply = False
                deny_reason = "photo_not_verified"
            elif await get_host_record_for_user(db, cc, user_id):
                can_apply = False
                deny_reason = "already_host"

    return {
        "canApplyForOwner": can_apply,
        "denyReason": deny_reason,
        "hostApplicationStatus": pending_for_user,
        "ownerVacantDays": await _owner_vacant_days(db, cc),
        "applyMinMembers": APPLY_MIN_MEMBERS,
    }


async def _owner_vacant_days(db: AsyncSession, city_code: str) -> int:
    if await get_owner_host(db, city_code):
        return 0
    since = await _owner_vacant_since(db, city_code)
    if not since:
        return 0
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    return max(0, (datetime.now(UTC) - since).days)


async def submit_owner_application(
    db: AsyncSession,
    user: User,
    *,
    city_code: str,
    intro_text: str | None,
    member_count: int,
) -> CityGroupHostApplication:
    elig = await get_host_application_eligibility(
        db, city_code=city_code, member_count=member_count, user_id=user.id
    )
    if not elig["canApplyForOwner"]:
        raise HTTPException(status_code=400, detail=elig.get("denyReason") or "cannot apply")

    intro = (intro_text or "").strip()
    if intro:
        await assert_text_content_safe(user, intro, scene=SCENE_SOCIAL, strict=True)

    app = CityGroupHostApplication(
        city_code=normalize_city_code(city_code),
        user_id=user.id,
        application_type=APP_TYPE_OWNER,
        status=APP_STATUS_PENDING,
        intro_text=intro or None,
    )
    db.add(app)
    await db.flush()
    return app


async def owner_nominate_deputy(
    db: AsyncSession,
    user: User,
    *,
    city_code: str,
    target_user_id: str,
) -> CityGroupHostApplication:
    cc = normalize_city_code(city_code)
    owner_host = await get_host_record_for_user(db, cc, user.id)
    if not owner_host or owner_host.role != HOST_ROLE_OWNER:
        raise HTTPException(status_code=403, detail="Only owner can nominate deputy")

    try:
        target_pk = parse_public_user_id(target_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid user id") from exc

    if target_pk == user.id:
        raise HTTPException(status_code=400, detail="Cannot nominate yourself")

    target = await db.scalar(select(User).where(User.id == target_pk))
    if not target or target.status != "active":
        raise HTTPException(status_code=404, detail="User not found")

    if not await _user_joined_city_hall(db, cc, target_pk):
        raise HTTPException(status_code=400, detail="User not in city group")

    if await get_host_record_for_user(db, cc, target_pk):
        raise HTTPException(status_code=409, detail="User is already a host")

    dep_count = await db.scalar(
        select(func.count(CityGroupHost.id)).where(
            CityGroupHost.city_code == cc,
            CityGroupHost.role == HOST_ROLE_DEPUTY,
            CityGroupHost.status == HOST_STATUS_ACTIVE,
        )
    )
    if int(dep_count or 0) >= MAX_DEPUTIES:
        raise HTTPException(status_code=409, detail="Deputy limit reached")

    pending = await db.scalar(
        select(CityGroupHostApplication).where(
            CityGroupHostApplication.city_code == cc,
            CityGroupHostApplication.user_id == target_pk,
            CityGroupHostApplication.application_type == APP_TYPE_DEPUTY,
            CityGroupHostApplication.status == APP_STATUS_PENDING,
        )
    )
    if pending:
        raise HTTPException(status_code=409, detail="Nomination already pending")

    app = CityGroupHostApplication(
        city_code=cc,
        user_id=target_pk,
        application_type=APP_TYPE_DEPUTY,
        status=APP_STATUS_PENDING,
        nominator_user_id=user.id,
    )
    db.add(app)
    await touch_host_active(db, owner_host)
    await db.flush()
    return app


async def approve_host_application(
    db: AsyncSession,
    application_id: int,
    *,
    reviewer_admin_id: int,
) -> CityGroupHost:
    app = await db.scalar(
        select(CityGroupHostApplication).where(CityGroupHostApplication.id == application_id)
    )
    if not app or app.status != APP_STATUS_PENDING:
        raise HTTPException(status_code=404, detail="Application not found")

    role = HOST_ROLE_OWNER if app.application_type == APP_TYPE_OWNER else HOST_ROLE_DEPUTY
    host = await admin_appoint_host(
        db,
        city_code=app.city_code,
        user_id=app.user_id,
        role=role,
        appointed_by=reviewer_admin_id,
    )
    app.status = APP_STATUS_APPROVED
    app.reviewer_admin_id = reviewer_admin_id
    app.reviewed_at = datetime.now(UTC)
    await db.flush()
    return host


async def reject_host_application(
    db: AsyncSession,
    application_id: int,
    *,
    reviewer_admin_id: int,
    review_note: str | None = None,
) -> CityGroupHostApplication:
    app = await db.scalar(
        select(CityGroupHostApplication).where(CityGroupHostApplication.id == application_id)
    )
    if not app or app.status != APP_STATUS_PENDING:
        raise HTTPException(status_code=404, detail="Application not found")
    app.status = APP_STATUS_REJECTED
    app.reviewer_admin_id = reviewer_admin_id
    app.reviewed_at = datetime.now(UTC)
    app.review_note = (review_note or "").strip() or None
    await db.flush()
    return app


async def promote_oldest_deputy_to_owner(db: AsyncSession, city_code: str) -> CityGroupHost | None:
    cc = normalize_city_code(city_code)
    if await get_owner_host(db, cc):
        return None
    deputy = await db.scalar(
        select(CityGroupHost).where(
            CityGroupHost.city_code == cc,
            CityGroupHost.role == HOST_ROLE_DEPUTY,
            CityGroupHost.status == HOST_STATUS_ACTIVE,
        )
        .order_by(CityGroupHost.appointed_at.asc())
        .limit(1)
    )
    if not deputy:
        return None
    deputy.role = HOST_ROLE_OWNER
    deputy.last_active_at = datetime.now(UTC)
    await db.flush()
    return deputy


async def sweep_inactive_owners(db: AsyncSession, *, inactive_days: int = INACTIVE_OWNER_DAYS) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=inactive_days)
    rows = (
        await db.execute(
            select(CityGroupHost).where(
                CityGroupHost.role == HOST_ROLE_OWNER,
                CityGroupHost.status == HOST_STATUS_ACTIVE,
            )
        )
    ).scalars().all()
    count = 0
    for host in rows:
        last = host.last_active_at or host.appointed_at
        if last and last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        if last and last >= cutoff:
            continue
        host.status = HOST_STATUS_RESIGNED
        host.resigned_at = datetime.now(UTC)
        await promote_oldest_deputy_to_owner(db, host.city_code)
        count += 1
    await db.flush()
    return count


def _parse_activity_pk(activity_id: str) -> int:
    s = activity_id[4:] if activity_id.startswith("act_") else activity_id
    if not s.isdigit():
        raise ValueError("invalid activity id")
    return int(s)


async def host_recommend_activity(
    db: AsyncSession,
    user: User,
    *,
    city_code: str,
    activity_id: str,
) -> ActivityMessage:
    host = await assert_active_host(db, city_code, user.id)
    cc = normalize_city_code(city_code)
    try:
        act_pk = _parse_activity_pk(activity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid activityId") from exc

    activity = await db.scalar(select(Activity).where(Activity.id == act_pk))
    if not activity or activity.activity_kind != EVENT_ACTIVITY_KIND:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.activity_status not in ("published", "full"):
        raise HTTPException(status_code=400, detail="Activity not available")
    if not activity_city_code_matches(cc, activity.city_code or ""):
        raise HTTPException(status_code=400, detail="Activity city mismatch")
    if activity.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="Can only recommend your own activities")

    recent = await _count_recent_actions(db, host.id, "recommend_activity")
    if recent >= RECOMMEND_ACTIVITY_WEEKLY_LIMIT:
        raise HTTPException(status_code=429, detail="Recommend activity limit reached")

    city_hall = await get_city_hall_by_code(db, cc)
    if not city_hall:
        raise HTTPException(status_code=404, detail="City hall not found")

    payload = encode_activity_rec_payload(activity_id=activity.id, title=activity.title)
    message = ActivityMessage(
        activity_id=city_hall.id,
        sender_id=user.id,
        msg_type="activity_rec",
        text_content=payload,
        image_url=None,
    )
    db.add(message)
    await _log_action(
        db,
        host=host,
        actor_user_id=user.id,
        action="recommend_activity",
        detail=f"activity_id={activity.id}",
    )
    await touch_host_active(db, host)
    await db.flush()
    await db.refresh(message)
    await increment_chat_unread_for_message(db, city_hall, user.id)
    return message
