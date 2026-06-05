"""城市大群：lookup / join / 按省目录；会话与消息复用 ``/activities/act_*``。

``GET /lookup`` 仅查询，**不写库**。``POST /join`` 在无记录时由系统账号 **懒创建** 群（首个进群的请求触发）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user, get_optional_user
from app.db.session import get_db_session
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.city_group_host import CityGroupHost
from app.models.user import User
from app.schemas.city_group import (
    AdminAppointCityGroupHostData,
    AdminAppointCityGroupHostRequest,
    AdminCityGroupHostItem,
    AdminCityGroupHostListData,
    AdminUpdateCityGroupHostRequest,
    CityGroupHostContextData,
    CityGroupHostDeleteMessageRequest,
    CityGroupHostMuteData,
    CityGroupHostMuteRequest,
    CityGroupHostProfilePatchRequest,
    CityGroupHostSummary,
    CityGroupProfileData,
    CityHallCatalogCity,
    CityHallCatalogData,
    CityHallCatalogProvince,
    CityHallJoinData,
    CityHallJoinRequest,
    CityHallLookupData,
)
from app.schemas.common import APIResponse
from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z
from app.services.activity_enroll import enroll_user_in_activity
from app.services.china_province_meta import province_display_name
from app.services.city_group_host import (
    HOST_ROLE_OWNER,
    admin_appoint_host,
    admin_update_host_status,
    assert_active_host,
    build_city_group_profile,
    get_active_hosts,
    get_city_hall_by_code,
    get_owner_host,
    host_delete_message,
    host_mute_member,
    host_summary_from_row,
    parse_public_user_id,
    patch_host_profile,
)
from app.services.city_hall import (
    CITY_HALL_ACTIVITY_KIND,
    get_or_create_city_hall_activity,
    is_city_hall_activity,
    normalize_city_code,
)
from app.services.city_hall_region_catalog import load_static_prefecture_blocks

router = APIRouter(prefix="/city-groups", tags=["city-groups"])
logger = logging.getLogger(__name__)


async def _member_count(db: AsyncSession, activity_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count(ActivityEnrollment.id)).where(
                ActivityEnrollment.activity_id == activity_id,
                ActivityEnrollment.status == "joined",
            )
        )
        or 0
    )


def _parse_activity_id(activity_id: str) -> int:
    s = activity_id[4:] if activity_id.startswith("act_") else activity_id
    if not s.isdigit():
        raise HTTPException(status_code=400, detail="invalid activityId")
    return int(s)


async def _owner_map_by_cities(db: AsyncSession) -> dict[str, tuple[CityGroupHost, User]]:
    rows = await db.execute(
        select(CityGroupHost, User)
        .join(User, User.id == CityGroupHost.user_id)
        .where(
            CityGroupHost.role == HOST_ROLE_OWNER,
            CityGroupHost.status == HOST_STATUS_ACTIVE,
        )
    )
    out: dict[str, tuple[CityGroupHost, User]] = {}
    for host, user in rows.all():
        out[host.city_code] = (host, user)
    return out


async def _lookup_host_fields(
    db: AsyncSession,
    city_code: str,
    current_user_id: int | None,
) -> dict:
    owner_row = await get_owner_host(db, city_code)
    owner = None
    announcement = None
    welcome_text = None
    current_user_host_role = None
    if owner_row:
        ou = await db.scalar(select(User).where(User.id == owner_row.user_id))
        if ou:
            owner = CityGroupHostSummary(**await host_summary_from_row(owner_row, ou))
        announcement = owner_row.announcement
        welcome_text = owner_row.welcome_text
    if current_user_id:
        for h, _u in await get_active_hosts(db, city_code):
            if h.user_id == current_user_id:
                current_user_host_role = h.role
                break
    return {
        "owner": owner,
        "announcement": announcement,
        "welcomeText": welcome_text,
        "currentUserHostRole": current_user_host_role,
    }


@router.get("/catalog")
async def city_hall_catalog(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    optional_user: User | None = Depends(get_optional_user),
) -> APIResponse[CityHallCatalogData]:
    """全国地级市目录（静态 JSON）与已开通大群合并：按省分组，每市展示人数或「未开通」。"""
    if optional_user:
        request.state.user_id = optional_user.id

    static_blocks = load_static_prefecture_blocks()
    owner_map = await _owner_map_by_cities(db)

    rows = (
        (await db.execute(select(Activity).where(Activity.activity_kind == CITY_HALL_ACTIVITY_KIND)))
        .scalars()
        .all()
    )
    act_by_code: dict[str, Activity] = {}
    for a in rows:
        key = (a.city_hall_city_code or a.city_code or "").strip()
        if key:
            act_by_code[key] = a

    ids = [a.id for a in rows]
    count_map: dict[int, int] = {}
    joined_ids: set[int] = set()
    if ids:
        cnt_rows = await db.execute(
            select(ActivityEnrollment.activity_id, func.count(ActivityEnrollment.id))
            .where(
                ActivityEnrollment.activity_id.in_(ids),
                ActivityEnrollment.status == "joined",
            )
            .group_by(ActivityEnrollment.activity_id)
        )
        count_map = {int(aid): int(c) for aid, c in cnt_rows.all()}

        if optional_user:
            jr = await db.execute(
                select(ActivityEnrollment.activity_id).where(
                    ActivityEnrollment.user_id == optional_user.id,
                    ActivityEnrollment.activity_id.in_(ids),
                    ActivityEnrollment.status == "joined",
                )
            )
            joined_ids = {int(r[0]) for r in jr.all()}

    provinces: list[CityHallCatalogProvince] = []
    for blk in static_blocks:
        pr_code = blk["provinceCode"]
        pr_name = province_display_name(pr_code)
        cities_out: list[CityHallCatalogCity] = []
        for c in blk["cities"]:
            cc = c["cityCode"]
            nm = c["cityName"]
            act = act_by_code.get(cc)
            owner_nick = None
            if cc in owner_map:
                owner_nick = owner_map[cc][1].nickname
            if act:
                cnt = count_map.get(act.id, 0)
                j = optional_user is not None and act.id in joined_ids
                cities_out.append(
                    CityHallCatalogCity(
                        cityCode=cc,
                        cityName=nm,
                        displayName=act.title,
                        memberCount=cnt,
                        activityId=f"act_{act.id}",
                        joined=j if optional_user else None,
                        ownerNickname=owner_nick,
                    )
                )
            else:
                cities_out.append(
                    CityHallCatalogCity(
                        cityCode=cc,
                        cityName=nm,
                        displayName=f"{nm} · 城市大群",
                        memberCount=0,
                        activityId=None,
                        joined=None,
                        ownerNickname=owner_nick,
                    )
                )
        provinces.append(
            CityHallCatalogProvince(
                provinceCode=pr_code,
                provinceName=pr_name,
                cities=cities_out,
            )
        )

    return APIResponse(data=CityHallCatalogData(provinces=provinces))


@router.get("/lookup")
async def lookup_city_hall(
    request: Request,
    cityCode: str = Query(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db_session),
    optional_user: User | None = Depends(get_optional_user),
) -> APIResponse[CityHallLookupData]:
    """仅查询是否已有大群及人数；**不会**自动建群。"""
    try:
        cc = normalize_city_code(cityCode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid cityCode") from exc

    if optional_user:
        request.state.user_id = optional_user.id

    row = await get_city_hall_by_code(db, cc)
    if not row:
        host_fields = await _lookup_host_fields(db, cc, optional_user.id if optional_user else None)
        return APIResponse(
            data=CityHallLookupData(
                exists=False,
                cityCode=cc,
                displayName="",
                memberCount=0,
                joined=False if optional_user else None,
                activityId=None,
                activityKind="event",
                **host_fields,
            )
        )

    cnt = await _member_count(db, row.id)
    joined: bool | None = None
    if optional_user:
        en = await db.scalar(
            select(ActivityEnrollment).where(
                ActivityEnrollment.activity_id == row.id,
                ActivityEnrollment.user_id == optional_user.id,
                ActivityEnrollment.status == "joined",
            )
        )
        joined = en is not None

    host_fields = await _lookup_host_fields(db, cc, optional_user.id if optional_user else None)
    return APIResponse(
        data=CityHallLookupData(
            exists=True,
            cityCode=cc,
            displayName=row.title,
            memberCount=cnt,
            joined=joined,
            activityId=f"act_{row.id}",
            activityKind="city_hall",
            **host_fields,
        )
    )


@router.get("/profile")
async def city_group_profile(
    request: Request,
    cityCode: str = Query(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db_session),
    optional_user: User | None = Depends(get_optional_user),
) -> APIResponse[CityGroupProfileData]:
    try:
        cc = normalize_city_code(cityCode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid cityCode") from exc

    if optional_user:
        request.state.user_id = optional_user.id

    row = await get_city_hall_by_code(db, cc)
    cnt = await _member_count(db, row.id) if row else 0
    profile = await build_city_group_profile(
        db,
        cc,
        member_count=cnt,
        display_name=row.title if row else "",
        activity_id=f"act_{row.id}" if row else None,
        current_user_id=optional_user.id if optional_user else None,
    )
    return APIResponse(data=CityGroupProfileData(**profile))


@router.get("/host-context")
async def city_group_host_context(
    request: Request,
    activityId: str = Query(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[CityGroupHostContextData]:
    request.state.user_id = current_user.id
    activity_pk = _parse_activity_id(activityId)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity or not is_city_hall_activity(activity):
        raise HTTPException(status_code=404, detail="City hall not found")

    cc = (activity.city_hall_city_code or activity.city_code or "").strip()
    if not cc:
        raise HTTPException(status_code=500, detail="invalid city hall")

    profile = await build_city_group_profile(
        db,
        cc,
        activity_id=f"act_{activity.id}",
        current_user_id=current_user.id,
    )
    host_ids = []
    if profile.get("owner"):
        host_ids.append(profile["owner"]["userId"])
    for d in profile.get("deputies") or []:
        host_ids.append(d["userId"])

    return APIResponse(
        data=CityGroupHostContextData(
            cityCode=cc,
            activityId=f"act_{activity.id}",
            owner=CityGroupHostSummary(**profile["owner"]) if profile.get("owner") else None,
            deputies=[CityGroupHostSummary(**d) for d in profile.get("deputies") or []],
            currentUserHostRole=profile.get("currentUserHostRole"),
            canModerate=profile.get("currentUserHostRole") is not None,
            hostUserIds=host_ids,
        )
    )


@router.patch("/me/host-profile")
async def patch_my_host_profile(
    request: Request,
    payload: CityGroupHostProfilePatchRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[CityGroupProfileData]:
    request.state.user_id = current_user.id
    await assert_active_host(db, payload.cityCode, current_user.id)
    await patch_host_profile(
        db,
        current_user,
        city_code=payload.cityCode,
        welcome_text=payload.welcomeText,
        announcement=payload.announcement,
        clear_welcome=payload.clearWelcome,
        clear_announcement=payload.clearAnnouncement,
    )
    await db.commit()

    row = await get_city_hall_by_code(db, payload.cityCode)
    cnt = await _member_count(db, row.id) if row else 0
    profile = await build_city_group_profile(
        db,
        payload.cityCode,
        member_count=cnt,
        display_name=row.title if row else "",
        activity_id=f"act_{row.id}" if row else None,
        current_user_id=current_user.id,
    )
    return APIResponse(data=CityGroupProfileData(**profile))


@router.post("/me/messages/{message_id}/delete")
async def host_delete_city_message(
    request: Request,
    message_id: str,
    payload: CityGroupHostDeleteMessageRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    request.state.user_id = current_user.id
    await host_delete_message(
        db,
        current_user,
        city_code=payload.cityCode,
        message_id=message_id,
    )
    await db.commit()
    return APIResponse(data={"ok": True})


@router.post("/me/members/mute")
async def host_mute_city_member(
    request: Request,
    payload: CityGroupHostMuteRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[CityGroupHostMuteData]:
    request.state.user_id = current_user.id
    until = await host_mute_member(
        db,
        current_user,
        city_code=payload.cityCode,
        target_user_id=payload.userId,
    )
    await db.commit()
    return APIResponse(
        data=CityGroupHostMuteData(mutedUntil=datetime_to_rfc3339_utc_z(until) or "")
    )


@router.post("/join")
async def join_city_hall(
    request: Request,
    payload: CityHallJoinRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[CityHallJoinData]:
    """若无该城大群则 **系统账号创建** 后再报名；管理员为系统内置账号。"""
    if current_user.status != "active":
        raise HTTPException(status_code=403, detail="User is restricted")
    try:
        cc = normalize_city_code(payload.cityCode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid cityCode") from exc

    lbl = (payload.cityLabel or "").strip() or None
    activity = await get_or_create_city_hall_activity(
        db, cc, city_label=lbl, log_user_id=current_user.id
    )
    if not is_city_hall_activity(activity):
        raise HTTPException(status_code=500, detail="invalid city hall state")

    enrollment = await enroll_user_in_activity(
        db, current_user.id, activity, raise_if_already_joined=False
    )
    from app.services.growth_trust import grant_pending_referral_rewards, on_qualified_action

    await on_qualified_action(db, current_user.id, "city_hall_join")
    await grant_pending_referral_rewards(db)
    cnt = await _member_count(db, activity.id)

    logger.info(
        "city_hall_join user_id=%s request_id=%s activity_id=%s city=%s",
        current_user.id,
        getattr(request.state, "request_id", ""),
        activity.id,
        cc,
    )

    return APIResponse(
        data=CityHallJoinData(
            cityCode=cc,
            displayName=activity.title,
            memberCount=cnt,
            joined=True,
            activityId=f"act_{activity.id}",
            enrollmentId=f"enr_{enrollment.id}",
        )
    )


admin_router = APIRouter(prefix="/admin/city-group-hosts", tags=["admin-city-group-hosts"])


@admin_router.get("")
async def admin_list_city_group_hosts(
    cityCode: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_admin_user),
) -> APIResponse[AdminCityGroupHostListData]:
    filters = []
    if cityCode:
        filters.append(CityGroupHost.city_code == normalize_city_code(cityCode))
    if status:
        filters.append(CityGroupHost.status == status)

    total = int(
        await db.scalar(select(func.count(CityGroupHost.id)).where(*filters)) or 0
    )
    rows = await db.execute(
        select(CityGroupHost, User)
        .join(User, User.id == CityGroupHost.user_id)
        .where(*filters)
        .order_by(CityGroupHost.id.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
    )
    items = [
        AdminCityGroupHostItem(
            id=h.id,
            cityCode=h.city_code,
            userId=f"u_{u.id}",
            nickname=u.nickname,
            role=h.role,
            status=h.status,
            appointedAt=datetime_to_rfc3339_utc_z(h.appointed_at) or "",
        )
        for h, u in rows.all()
    ]
    return APIResponse(
        data=AdminCityGroupHostListData(
            list=items, total=total, page=page, pageSize=pageSize
        )
    )


@admin_router.post("")
async def admin_appoint_city_group_host(
    payload: AdminAppointCityGroupHostRequest,
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
) -> APIResponse[AdminAppointCityGroupHostData]:
    try:
        uid = parse_public_user_id(payload.userId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid userId") from exc

    host = await admin_appoint_host(
        db,
        city_code=payload.cityCode,
        user_id=uid,
        role=payload.role,
        appointed_by=admin_user.id,
    )
    await db.commit()
    return APIResponse(
        data=AdminAppointCityGroupHostData(
            id=host.id,
            cityCode=host.city_code,
            userId=f"u_{host.user_id}",
            role=host.role,
            status=host.status,
        )
    )


@admin_router.patch("/{host_id}")
async def admin_patch_city_group_host(
    host_id: int,
    payload: AdminUpdateCityGroupHostRequest,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_admin_user),
) -> APIResponse[AdminAppointCityGroupHostData]:
    host = await admin_update_host_status(db, host_id, payload.status)
    await db.commit()
    return APIResponse(
        data=AdminAppointCityGroupHostData(
            id=host.id,
            cityCode=host.city_code,
            userId=f"u_{host.user_id}",
            role=host.role,
            status=host.status,
        )
    )
