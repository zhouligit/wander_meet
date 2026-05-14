from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.services.city_hall import EVENT_ACTIVITY_KIND, is_city_hall_activity
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.activity_message import ActivityMessage
from app.models.place_activity_alert import PlaceActivityAlert
from app.models.user import User
from app.models.user_chat_read import UserChatRead
from app.schemas.common import APIResponse
from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z
from app.schemas.me import (
    MeData,
    MyActivitiesData,
    MyActivitiesItem,
    MyChatsData,
    MyChatItem,
    MyStatsData,
    PremiumData,
    UpdateMeRequest,
    VerificationSummary,
)
from app.schemas.place_activity import (
    CreatePlaceActivityAlertRequest,
    PlaceActivityAlertCreateData,
    PlaceActivityAlertItem,
    PlaceActivityAlertListData,
)
from app.services.user_profile_fields import bio_from_user, tags_from_user

router = APIRouter(prefix="/me", tags=["me"])

EPOCH_UTC = datetime(1970, 1, 1, tzinfo=UTC)

_STAY_KINDS = frozenset({"indefinite", "fixed_dates"})
_TRAVELER_ROLE_MAX = 2


def _phone_masked(user: User) -> str:
    p = user.phone
    if p and len(p) >= 11:
        return f"{p[:3]}****{p[-4:]}"
    if len(user.phone_hash) >= 4:
        return f"***{user.phone_hash[-4:]}"
    return "***********"


def _traveler_roles_list(user: User) -> list[str]:
    raw = user.traveler_roles
    if not raw or not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw[:_TRAVELER_ROLE_MAX]:
        if isinstance(x, str) and x.strip():
            out.append(x.strip()[:48])
    return out[:_TRAVELER_ROLE_MAX]


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    s = str(value).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def build_me_data(user: User) -> MeData:
    g = user.gender
    if g is not None and g not in ("male", "female", "unspecified"):
        g = None
    np = user.notify_prefs if isinstance(user.notify_prefs, dict) else None
    return MeData(
        userId=f"u_{user.id}",
        phoneMasked=_phone_masked(user),
        nickname=user.nickname,
        avatarUrl=user.avatar_url,
        gender=g,
        bio=bio_from_user(user),
        tags=tags_from_user(user),
        status=user.status,
        verification=VerificationSummary(status="none", canCreateActivity=True),
        countryCode=(user.country_code or "").strip() or None,
        travelerRoles=_traveler_roles_list(user),
        currentPlace=(user.current_place or "").strip() or None,
        stayKind=user.stay_kind,
        stayEndAt=datetime_to_rfc3339_utc_z(user.stay_end_at),
        acquisitionSource=(user.acquisition_source or "").strip() or None,
        notifyPrefs=np,
        showDistance=bool(user.show_distance),
        onboardingCompletedAt=datetime_to_rfc3339_utc_z(user.onboarding_completed_at),
    )


@router.get("/stats")
async def my_stats(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MyStatsData]:
    organized = await db.scalar(
        select(func.count(Activity.id)).where(
            Activity.organizer_id == current_user.id,
            Activity.activity_kind == EVENT_ACTIVITY_KIND,
        )
    )
    joined = await db.scalar(
        select(func.count(Activity.id))
        .select_from(Activity)
        .join(ActivityEnrollment, ActivityEnrollment.activity_id == Activity.id)
        .where(
            ActivityEnrollment.user_id == current_user.id,
            ActivityEnrollment.status == "joined",
        )
    )
    return APIResponse(
        data=MyStatsData(
            joinedCount=int(joined or 0),
            organizedCount=int(organized or 0),
        )
    )


@router.get("")
async def get_me(current_user: User = Depends(get_current_user)) -> APIResponse[MeData]:
    return APIResponse(data=build_me_data(current_user))


@router.patch("")
async def update_me(
    payload: UpdateMeRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MeData]:
    if payload.nickname is not None:
        nn = (payload.nickname or "").strip()
        if not nn:
            raise HTTPException(status_code=400, detail="nickname is required when provided")
        current_user.nickname = nn[:32]
    if payload.avatarUrl is not None:
        current_user.avatar_url = payload.avatarUrl
    if payload.bio is not None:
        b = (payload.bio or "").strip()
        current_user.bio = b[:2000] if b else None
    if payload.tags is not None:
        current_user.tags = list(payload.tags)[:20]
    if payload.gender is not None:
        if current_user.gender is not None:
            if payload.gender != current_user.gender:
                raise HTTPException(status_code=400, detail="性别提交后不可修改")
        else:
            current_user.gender = payload.gender
    if payload.countryCode is not None:
        cc = (payload.countryCode or "").strip().upper()
        current_user.country_code = cc[:8] if cc else None
    if payload.travelerRoles is not None:
        roles: list[str] = []
        for x in payload.travelerRoles[:_TRAVELER_ROLE_MAX]:
            if isinstance(x, str) and x.strip():
                roles.append(x.strip()[:48])
        current_user.traveler_roles = roles[:_TRAVELER_ROLE_MAX] if roles else None
    if payload.currentPlace is not None:
        cp = (payload.currentPlace or "").strip()
        current_user.current_place = cp[:256] if cp else None
    if payload.stayKind is not None:
        sk = (payload.stayKind or "").strip()
        if sk and sk not in _STAY_KINDS:
            raise HTTPException(status_code=400, detail="stayKind is invalid")
        current_user.stay_kind = sk if sk else None
    if payload.stayEndAt is not None:
        if not str(payload.stayEndAt).strip():
            current_user.stay_end_at = None
        else:
            current_user.stay_end_at = _parse_iso_datetime(payload.stayEndAt)
    if payload.acquisitionSource is not None:
        ac = (payload.acquisitionSource or "").strip()
        current_user.acquisition_source = ac[:64] if ac else None
    if payload.notifyPrefs is not None:
        if not isinstance(payload.notifyPrefs, dict):
            raise HTTPException(status_code=400, detail="notifyPrefs must be an object")
        current_user.notify_prefs = dict(payload.notifyPrefs)
    if payload.showDistance is not None:
        current_user.show_distance = bool(payload.showDistance)
    if payload.completeOnboarding is True:
        current_user.onboarding_completed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(current_user)
    return APIResponse(data=build_me_data(current_user))


@router.get("/activities")
async def my_activities(
    role: str = Query(..., pattern="^(organized|joined)$"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MyActivitiesData]:
    if role == "organized":
        base_stmt = select(Activity).where(
            Activity.organizer_id == current_user.id,
            Activity.activity_kind == EVENT_ACTIVITY_KIND,
        )
        total = (
            await db.execute(
                select(func.count(Activity.id)).where(
                    Activity.organizer_id == current_user.id,
                    Activity.activity_kind == EVENT_ACTIVITY_KIND,
                )
            )
        ).scalar_one()
        rows = (
            (
                await db.execute(
                    base_stmt.order_by(Activity.start_at.desc())
                    .offset((page - 1) * pageSize)
                    .limit(pageSize)
                )
            )
            .scalars()
            .all()
        )
    else:
        joined_filter = and_(
            ActivityEnrollment.user_id == current_user.id,
            ActivityEnrollment.status == "joined",
        )
        total = (
            await db.execute(
                select(func.count(Activity.id))
                .select_from(Activity)
                .join(ActivityEnrollment, ActivityEnrollment.activity_id == Activity.id)
                .where(joined_filter)
            )
        ).scalar_one()
        rows = (
            (
                await db.execute(
                    select(Activity)
                    .join(ActivityEnrollment, ActivityEnrollment.activity_id == Activity.id)
                    .where(joined_filter)
                    .order_by(
                        case((Activity.activity_kind == "city_hall", 0), else_=1),
                        Activity.start_at.desc(),
                    )
                    .offset((page - 1) * pageSize)
                    .limit(pageSize)
                )
            )
            .scalars()
            .all()
        )

    data = MyActivitiesData(
        list=[
            MyActivitiesItem(
                activityId=f"act_{a.id}",
                activityKind=a.activity_kind,
                title=a.title,
                startAt=a.start_at,
                locationName=a.location_name,
                categoryId=a.category_id,
                activityStatus=a.activity_status,
            )
            for a in rows
        ],
        total=total,
        page=page,
        pageSize=pageSize,
    )
    return APIResponse(data=data)


@router.get("/premium")
async def my_premium(_: User = Depends(get_current_user)) -> APIResponse[PremiumData]:
    return APIResponse(data=PremiumData(enabled=False, sku=[]))


@router.get("/chats")
async def my_chats(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MyChatsData]:
    joined_activity_ids_subq = (
        select(ActivityEnrollment.activity_id)
        .where(
            ActivityEnrollment.user_id == current_user.id,
            ActivityEnrollment.status == "joined",
        )
        .subquery()
    )

    last_msg_sq = (
        select(
            ActivityMessage.activity_id.label("aid"),
            func.max(ActivityMessage.created_at).label("last_msg_at"),
        )
        .where(ActivityMessage.activity_id.in_(select(joined_activity_ids_subq.c.activity_id)))
        .group_by(ActivityMessage.activity_id)
        .subquery()
    )

    total = (
        await db.execute(
            select(func.count(Activity.id)).where(
                Activity.id.in_(select(joined_activity_ids_subq.c.activity_id))
            )
        )
    ).scalar_one()

    activities = (
        (
            await db.execute(
                select(Activity)
                .join(ActivityEnrollment, ActivityEnrollment.activity_id == Activity.id)
                .where(
                    ActivityEnrollment.user_id == current_user.id,
                    ActivityEnrollment.status == "joined",
                )
                .outerjoin(last_msg_sq, last_msg_sq.c.aid == Activity.id)
                .order_by(
                    case((Activity.activity_kind == "city_hall", 0), else_=1),
                    func.coalesce(last_msg_sq.c.last_msg_at, EPOCH_UTC).desc(),
                    Activity.id.desc(),
                )
                .offset((page - 1) * pageSize)
                .limit(pageSize)
            )
        )
        .scalars()
        .all()
    )
    if not activities:
        return APIResponse(data=MyChatsData(list=[], total=0, page=page, pageSize=pageSize))

    activity_ids = [a.id for a in activities]
    member_rows = await db.execute(
        select(ActivityEnrollment.activity_id, func.count(ActivityEnrollment.id))
        .where(
            ActivityEnrollment.activity_id.in_(activity_ids),
            ActivityEnrollment.status == "joined",
        )
        .group_by(ActivityEnrollment.activity_id)
    )
    member_count_map = {activity_id: cnt for activity_id, cnt in member_rows.all()}

    latest_msg_id_subq = (
        select(
            ActivityMessage.activity_id.label("activity_id"),
            func.max(ActivityMessage.id).label("last_message_id"),
        )
        .where(ActivityMessage.activity_id.in_(activity_ids))
        .group_by(ActivityMessage.activity_id)
        .subquery()
    )
    latest_rows = await db.execute(
        select(ActivityMessage)
        .join(latest_msg_id_subq, ActivityMessage.id == latest_msg_id_subq.c.last_message_id)
    )
    latest_message_map = {row.activity_id: row for row in latest_rows.scalars().all()}

    unread_rows = await db.execute(
        select(ActivityMessage.activity_id, func.count(ActivityMessage.id))
        .outerjoin(
            UserChatRead,
            and_(
                UserChatRead.activity_id == ActivityMessage.activity_id,
                UserChatRead.user_id == current_user.id,
            ),
        )
        .where(
            ActivityMessage.activity_id.in_(activity_ids),
            ActivityMessage.id > func.coalesce(UserChatRead.last_read_message_id, 0),
        )
        .group_by(ActivityMessage.activity_id)
    )
    unread_map = {activity_id: count for activity_id, count in unread_rows.all()}

    chat_items: list[MyChatItem] = []
    for activity in activities:
        last_msg = latest_message_map.get(activity.id)

        if last_msg is None:
            last_message = None
            last_message_at = None
        elif last_msg.msg_type == "text":
            last_message = last_msg.text_content or ""
            last_message_at = last_msg.created_at
        else:
            last_message = "[图片]"
            last_message_at = last_msg.created_at

        unread_raw = int(unread_map.get(activity.id, 0))
        if is_city_hall_activity(activity):
            unread_raw = min(unread_raw, 99)
        chat_items.append(
            MyChatItem(
                activityId=f"act_{activity.id}",
                activityKind=activity.activity_kind,
                title=activity.title,
                activityStatus=activity.activity_status,
                memberCount=int(member_count_map.get(activity.id, 0)),
                lastMessage=last_message,
                lastMessageAt=last_message_at,
                unreadCount=unread_raw,
            )
        )

    return APIResponse(data=MyChatsData(list=chat_items, total=total, page=page, pageSize=pageSize))


@router.patch("/chats/{activity_id}/read")
async def mark_chat_read(
    activity_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict[str, int]]:
    if activity_id.startswith("act_"):
        activity_id = activity_id[4:]
    if not activity_id.isdigit():
        return APIResponse(code=400, message="invalid activity id", data={"updatedCount": 0})
    activity_pk = int(activity_id)

    last_msg_id = await db.scalar(
        select(func.max(ActivityMessage.id)).where(ActivityMessage.activity_id == activity_pk)
    )
    last_msg_id = int(last_msg_id or 0)

    row = await db.scalar(
        select(UserChatRead).where(
            UserChatRead.user_id == current_user.id, UserChatRead.activity_id == activity_pk
        )
    )
    if row:
        row.last_read_message_id = last_msg_id
    else:
        row = UserChatRead(
            user_id=current_user.id,
            activity_id=activity_pk,
            last_read_message_id=last_msg_id,
        )
        db.add(row)
    await db.commit()
    return APIResponse(data={"updatedCount": 1})


@router.post("/avatar/upload-url")
async def avatar_upload_url(
    contentType: str,
    fileExt: str,
    _: User = Depends(get_current_user),
) -> APIResponse[dict]:
    # v0.1 placeholder for OSS pre-signed upload integration.
    return APIResponse(
        data={
            "uploadUrl": "https://upload.wandermeet.local/placeholder",
            "objectKey": f"wm/avatar/tmp/avatar.{fileExt}",
            "headers": {"Content-Type": contentType},
        }
    )


@router.get("/place-activity-alerts")
async def list_my_place_activity_alerts(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PlaceActivityAlertListData]:
    rows = (
        (
            await db.execute(
                select(PlaceActivityAlert)
                .where(
                    PlaceActivityAlert.user_id == current_user.id,
                    PlaceActivityAlert.status == "active",
                )
                .order_by(PlaceActivityAlert.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return APIResponse(
        data=PlaceActivityAlertListData(
            list=[
                PlaceActivityAlertItem(
                    alertId=f"pal_{r.id}",
                    cityCode=r.city_code,
                    placeLabel=r.place_label,
                    categoryId=r.category_id or "",
                    dateRange=r.date_range,
                    status=r.status,
                    createdAt=r.created_at,
                )
                for r in rows
            ],
        )
    )


@router.post("/place-activity-alerts")
async def create_place_activity_alert(
    payload: CreatePlaceActivityAlertRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PlaceActivityAlertCreateData]:
    cc = (payload.cityCode or "").strip()
    if not cc or len(cc) > 16:
        raise HTTPException(status_code=400, detail="invalid cityCode")
    lbl = (payload.placeLabel or "").strip()[:128]
    cat = ((payload.categoryId or "").strip()[:32]) if payload.categoryId else ""
    dr = payload.dateRange or "all"

    existing = await db.scalar(
        select(PlaceActivityAlert).where(
            PlaceActivityAlert.user_id == current_user.id,
            PlaceActivityAlert.city_code == cc,
            PlaceActivityAlert.category_id == cat,
            PlaceActivityAlert.date_range == dr,
            PlaceActivityAlert.status == "active",
        )
    )
    if existing:
        return APIResponse(
            data=PlaceActivityAlertCreateData(
                alertId=f"pal_{existing.id}",
                cityCode=existing.city_code,
                placeLabel=existing.place_label,
                categoryId=existing.category_id or "",
                dateRange=existing.date_range,
                createdAt=existing.created_at,
            )
        )

    row = PlaceActivityAlert(
        user_id=current_user.id,
        city_code=cc,
        place_label=lbl or cc,
        category_id=cat,
        date_range=dr,
        status="active",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return APIResponse(
        data=PlaceActivityAlertCreateData(
            alertId=f"pal_{row.id}",
            cityCode=row.city_code,
            placeLabel=row.place_label,
            categoryId=row.category_id or "",
            dateRange=row.date_range,
            createdAt=row.created_at,
        )
    )


@router.delete("/place-activity-alerts/{alert_id}")
async def delete_place_activity_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    raw = alert_id.strip()
    if raw.startswith("pal_"):
        raw = raw[4:]
    if not raw.isdigit():
        raise HTTPException(status_code=400, detail="invalid alert id")
    pk = int(raw)
    row = await db.scalar(
        select(PlaceActivityAlert).where(
            PlaceActivityAlert.id == pk,
            PlaceActivityAlert.user_id == current_user.id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    await db.delete(row)
    await db.commit()
    return APIResponse(data={"deleted": True})

