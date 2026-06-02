"""城市大群：lookup / join / 按省目录；会话与消息复用 ``/activities/act_*``。

``GET /lookup`` 仅查询，**不写库**。``POST /join`` 在无记录时由系统账号 **懒创建** 群（首个进群的请求触发）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.db.session import get_db_session
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.user import User
from app.schemas.city_group import (
    CityHallCatalogCity,
    CityHallCatalogData,
    CityHallCatalogProvince,
    CityHallJoinData,
    CityHallJoinRequest,
    CityHallLookupData,
)
from app.schemas.common import APIResponse
from app.services.activity_enroll import enroll_user_in_activity
from app.services.china_province_meta import province_display_name
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

    row = await db.scalar(
        select(Activity).where(
            Activity.activity_kind == CITY_HALL_ACTIVITY_KIND,
            Activity.city_hall_city_code == cc,
        )
    )
    if not row:
        return APIResponse(
            data=CityHallLookupData(
                exists=False,
                cityCode=cc,
                displayName="",
                memberCount=0,
                joined=False if optional_user else None,
                activityId=None,
                activityKind="event",
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

    return APIResponse(
        data=CityHallLookupData(
            exists=True,
            cityCode=cc,
            displayName=row.title,
            memberCount=cnt,
            joined=joined,
            activityId=f"act_{row.id}",
            activityKind="city_hall",
        )
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
