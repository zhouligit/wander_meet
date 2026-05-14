"""城市大群：lookup / join / 按省目录；会话与消息复用 ``/activities/act_*``。

``GET /lookup`` 仅查询，**不写库**。``POST /join`` 在无记录时由系统账号 **懒创建** 群（首个进群的请求触发）。
"""

from __future__ import annotations

import logging
from collections import defaultdict

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
from app.services.china_province_meta import infer_province_code, province_display_name
from app.services.city_hall import (
    CITY_HALL_ACTIVITY_KIND,
    city_hall_short_label,
    get_or_create_city_hall_activity,
    is_city_hall_activity,
    normalize_city_code,
)

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
    """已创建的城市大群目录：按省分组，省内按 ``city_hall_sort_key``、城市码排序。"""
    if optional_user:
        request.state.user_id = optional_user.id

    rows = (
        (
            await db.execute(
                select(Activity)
                .where(Activity.activity_kind == CITY_HALL_ACTIVITY_KIND)
                .order_by(
                    Activity.city_hall_province_code.asc(),
                    Activity.city_hall_sort_key.asc(),
                    Activity.city_hall_city_code.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return APIResponse(data=CityHallCatalogData(provinces=[]))

    ids = [a.id for a in rows]
    cnt_rows = await db.execute(
        select(ActivityEnrollment.activity_id, func.count(ActivityEnrollment.id))
        .where(
            ActivityEnrollment.activity_id.in_(ids),
            ActivityEnrollment.status == "joined",
        )
        .group_by(ActivityEnrollment.activity_id)
    )
    count_map = {int(aid): int(c) for aid, c in cnt_rows.all()}

    joined_ids: set[int] = set()
    if optional_user:
        jr = await db.execute(
            select(ActivityEnrollment.activity_id).where(
                ActivityEnrollment.user_id == optional_user.id,
                ActivityEnrollment.activity_id.in_(ids),
                ActivityEnrollment.status == "joined",
            )
        )
        joined_ids = {int(r[0]) for r in jr.all()}

    buckets: dict[str, list[Activity]] = defaultdict(list)
    for a in rows:
        prov = (a.city_hall_province_code or "").strip() or infer_province_code(
            a.city_hall_city_code or ""
        )
        buckets[prov].append(a)

    province_order = sorted(buckets.keys())
    provinces: list[CityHallCatalogProvince] = []
    for code in province_order:
        cities_act = sorted(
            buckets[code],
            key=lambda x: (
                (x.city_hall_sort_key or "").lower(),
                (x.city_hall_city_code or "").lower(),
            ),
        )
        cities: list[CityHallCatalogCity] = []
        for a in cities_act:
            cnt = count_map.get(a.id, 0)
            j = optional_user is not None and a.id in joined_ids
            cities.append(
                CityHallCatalogCity(
                    cityCode=a.city_hall_city_code or a.city_code,
                    cityName=city_hall_short_label(a.title),
                    displayName=a.title,
                    memberCount=cnt,
                    activityId=f"act_{a.id}",
                    joined=j if optional_user else None,
                )
            )
        provinces.append(
            CityHallCatalogProvince(
                provinceCode=code,
                provinceName=province_display_name(code),
                cities=cities,
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
