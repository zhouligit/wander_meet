import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.services.activity_query import (
    effective_activity_status,
    my_activities_all_order,
    my_activities_event_desc_order,
    my_activities_past_order,
    my_activities_upcoming_order,
    past_activity_condition,
    upcoming_activity_condition,
)
from app.services.user_cache import (
    get_cached_me_data,
    get_cached_me_stats,
    invalidate_user_cache,
    load_user_for_update,
    set_cached_me_data,
    set_cached_me_stats,
)
from app.services.chat_unread import get_chat_unread_counts, reset_chat_unread
from app.services.city_hall import (
    CITY_HALL_ACTIVITY_KIND,
    EVENT_ACTIVITY_KIND,
    is_city_hall_activity,
)
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.activity_message import ActivityMessage
from app.models.place_activity_alert import PlaceActivityAlert
from app.models.user import User
from app.models.user_feedback import UserFeedback
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
from app.schemas.feedback import CreateUserFeedbackRequest, UserFeedbackCreateData
from app.schemas.place_activity import (
    CreatePlaceActivityAlertRequest,
    PlaceActivityAlertCreateData,
    PlaceActivityAlertItem,
    PlaceActivityAlertListData,
)
from app.core.config import get_settings
from app.core.security import create_access_token
from app.schemas.auth import LoginUser
from app.schemas.phone_bind import BindPhoneData, BindPhoneSmsRequest, BindPhoneWechatRequest
from app.services.auth_refresh import issue_refresh_token
from app.services.phone_validation import parse_cn_mobile
from app.services.email_auth import user_has_email_account
from app.services.email_validation import mask_email
from app.services.user_phone_bind import bind_phone_to_user, mask_user_phone, user_has_phone
from app.services.user_profile_fields import bio_from_user, tags_from_user
from app.services.wechat_miniapp import WechatLoginError, get_phone_number_from_code
from app.db.session import redis_client

router = APIRouter(prefix="/me", tags=["me"])
logger = logging.getLogger(__name__)

EPOCH_UTC = datetime(1970, 1, 1, tzinfo=UTC)

_STAY_KINDS = frozenset({"indefinite", "fixed_dates"})
_TRAVELER_ROLE_MAX = 2


def _phone_masked(user: User) -> str:
    return mask_user_phone(user)


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
        phoneBound=user_has_phone(user),
        emailMasked=mask_email(user.email) if user_has_email_account(user) else "",
        emailBound=user_has_email_account(user),
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
    cached_stats = await get_cached_me_stats(current_user.id)
    if cached_stats is not None:
        return APIResponse(data=cached_stats)

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
    stats = MyStatsData(
        joinedCount=int(joined or 0),
        organizedCount=int(organized or 0),
    )
    await set_cached_me_stats(current_user.id, stats)
    return APIResponse(data=stats)


@router.get("")
async def get_me(current_user: User = Depends(get_current_user)) -> APIResponse[MeData]:
    cached = await get_cached_me_data(current_user.id)
    if cached is not None:
        return APIResponse(data=cached)
    data = build_me_data(current_user)
    await set_cached_me_data(current_user.id, data)
    return APIResponse(data=data)


@router.patch("")
async def update_me(
    payload: UpdateMeRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MeData]:
    user = await load_user_for_update(db, current_user.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.nickname is not None:
        nn = (payload.nickname or "").strip()
        if not nn:
            raise HTTPException(status_code=400, detail="nickname is required when provided")
        user.nickname = nn[:32]
    if payload.avatarUrl is not None:
        user.avatar_url = payload.avatarUrl
    if payload.bio is not None:
        b = (payload.bio or "").strip()
        user.bio = b[:2000] if b else None
    if payload.tags is not None:
        user.tags = list(payload.tags)[:20]
    if payload.gender is not None:
        if user.gender is not None:
            if payload.gender != user.gender:
                raise HTTPException(status_code=400, detail="性别提交后不可修改")
        else:
            user.gender = payload.gender
    if payload.countryCode is not None:
        cc = (payload.countryCode or "").strip().upper()
        user.country_code = cc[:8] if cc else None
    if payload.travelerRoles is not None:
        roles: list[str] = []
        for x in payload.travelerRoles[:_TRAVELER_ROLE_MAX]:
            if isinstance(x, str) and x.strip():
                roles.append(x.strip()[:48])
        user.traveler_roles = roles[:_TRAVELER_ROLE_MAX] if roles else None
    if payload.currentPlace is not None:
        cp = (payload.currentPlace or "").strip()
        user.current_place = cp[:256] if cp else None
    if payload.stayKind is not None:
        sk = (payload.stayKind or "").strip()
        if sk and sk not in _STAY_KINDS:
            raise HTTPException(status_code=400, detail="stayKind is invalid")
        user.stay_kind = sk if sk else None
    if payload.stayEndAt is not None:
        if not str(payload.stayEndAt).strip():
            user.stay_end_at = None
        else:
            user.stay_end_at = _parse_iso_datetime(payload.stayEndAt)
    if payload.acquisitionSource is not None:
        ac = (payload.acquisitionSource or "").strip()
        user.acquisition_source = ac[:64] if ac else None
    if payload.notifyPrefs is not None:
        if not isinstance(payload.notifyPrefs, dict):
            raise HTTPException(status_code=400, detail="notifyPrefs must be an object")
        user.notify_prefs = dict(payload.notifyPrefs)
    if payload.showDistance is not None:
        user.show_distance = bool(payload.showDistance)
    if payload.completeOnboarding is True:
        user.onboarding_completed_at = datetime.now(UTC)
    try:
        await db.commit()
    except OperationalError as exc:
        await db.rollback()
        logger.exception("update_me db error user_id=%s", user.id)
        err = str(getattr(exc, "orig", exc)).lower()
        if "unknown column" in err or "bio" in err:
            raise HTTPException(
                status_code=500,
                detail="数据库未迁移完整，请在服务器执行 alembic upgrade head",
            ) from exc
        raise HTTPException(status_code=500, detail="更新资料失败") from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception("update_me db error user_id=%s", user.id)
        raise HTTPException(status_code=500, detail="更新资料失败") from exc

    try:
        await invalidate_user_cache(user.id)
    except Exception:
        logger.warning("invalidate_user_cache failed user_id=%s", user.id, exc_info=True)

    return APIResponse(data=build_me_data(user))


def _my_activities_order(time_scope: str, now_utc: datetime):
    if time_scope == "past":
        return [my_activities_past_order()]
    if time_scope == "upcoming":
        return [my_activities_upcoming_order()]
    if time_scope == "all":
        return my_activities_all_order(now_utc)
    return [Activity.start_at.desc()]


def _joined_activities_order(
    activity_kind: str | None,
    time_scope: str,
    now_utc: datetime,
):
    if activity_kind == CITY_HALL_ACTIVITY_KIND:
        return [ActivityEnrollment.created_at.desc()]
    if activity_kind == EVENT_ACTIVITY_KIND:
        if time_scope == "past":
            return [my_activities_past_order()]
        if time_scope == "upcoming":
            return [my_activities_upcoming_order()]
        return [my_activities_event_desc_order()]
    return [
        case((Activity.activity_kind == CITY_HALL_ACTIVITY_KIND, 0), else_=1),
        *_my_activities_order(time_scope, now_utc),
    ]


def _my_activity_item(a: Activity, now_utc: datetime) -> MyActivitiesItem:
    return MyActivitiesItem(
        activityId=f"act_{a.id}",
        activityKind=a.activity_kind,
        title=a.title,
        startAt=a.start_at,
        endAt=a.end_at,
        locationName=a.location_name,
        categoryId=a.category_id,
        categoryLabel=(a.category_label or "").strip(),
        activityStatus=effective_activity_status(a, now_utc),
    )


@router.get("/activities")
async def my_activities(
    role: str = Query("joined", pattern="^(organized|joined|all)$"),
    timeScope: str = Query("all", pattern="^(all|past|upcoming)$"),
    activityKind: str | None = Query(
        None,
        pattern="^(city_hall|event)$",
        description="joined 时按类型筛选：city_hall 城市大群 / event 普通活动",
    ),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MyActivitiesData]:
    """
    我的活动列表。

    - ``role``: ``joined`` 已报名 / ``organized`` 我发起 / ``all`` 二者合并（仅普通活动）
    - ``timeScope``: ``all`` 不限 / ``past`` 已结束 / ``upcoming`` 未结束
    - ``activityKind``: ``joined`` 时可筛 ``city_hall`` / ``event``（分页列表用）
    """
    now_utc = datetime.now(UTC)
    time_filters: list = []
    if timeScope == "past":
        time_filters.append(past_activity_condition(now_utc))
    elif timeScope == "upcoming":
        time_filters.append(upcoming_activity_condition(now_utc))

    if role == "organized":
        scope = [
            Activity.organizer_id == current_user.id,
            Activity.activity_kind == EVENT_ACTIVITY_KIND,
            *time_filters,
        ]
        total = (await db.execute(select(func.count(Activity.id)).where(*scope))).scalar_one()
        rows = (
            (
                await db.execute(
                    select(Activity)
                    .where(*scope)
                    .order_by(*_my_activities_order(timeScope, now_utc))
                    .offset((page - 1) * pageSize)
                    .limit(pageSize)
                )
            )
            .scalars()
            .all()
        )
    elif role == "joined":
        joined_filter = and_(
            ActivityEnrollment.user_id == current_user.id,
            ActivityEnrollment.status == "joined",
            *time_filters,
        )
        if activityKind == CITY_HALL_ACTIVITY_KIND:
            joined_filter = and_(
                joined_filter,
                Activity.activity_kind == CITY_HALL_ACTIVITY_KIND,
            )
        elif activityKind == EVENT_ACTIVITY_KIND:
            joined_filter = and_(
                joined_filter,
                Activity.activity_kind == EVENT_ACTIVITY_KIND,
            )
        total_all = (
            await db.execute(
                select(func.count(Activity.id))
                .select_from(Activity)
                .join(ActivityEnrollment, ActivityEnrollment.activity_id == Activity.id)
                .where(
                    ActivityEnrollment.user_id == current_user.id,
                    ActivityEnrollment.status == "joined",
                    *time_filters,
                )
            )
        ).scalar_one()
        city_hall_count = (
            await db.execute(
                select(func.count(Activity.id))
                .select_from(Activity)
                .join(ActivityEnrollment, ActivityEnrollment.activity_id == Activity.id)
                .where(
                    ActivityEnrollment.user_id == current_user.id,
                    ActivityEnrollment.status == "joined",
                    *time_filters,
                    Activity.activity_kind == CITY_HALL_ACTIVITY_KIND,
                )
            )
        ).scalar_one()
        event_count = int(total_all or 0) - int(city_hall_count or 0)
        if activityKind == CITY_HALL_ACTIVITY_KIND:
            list_total = int(city_hall_count or 0)
        elif activityKind == EVENT_ACTIVITY_KIND:
            list_total = event_count
        else:
            list_total = int(total_all or 0)
        rows = (
            (
                await db.execute(
                    select(Activity)
                    .join(ActivityEnrollment, ActivityEnrollment.activity_id == Activity.id)
                    .where(joined_filter)
                    .order_by(*_joined_activities_order(activityKind, timeScope, now_utc))
                    .offset((page - 1) * pageSize)
                    .limit(pageSize)
                )
            )
            .scalars()
            .all()
        )
        data = MyActivitiesData(
            list=[_my_activity_item(a, now_utc) for a in rows],
            total=list_total,
            page=page,
            pageSize=pageSize,
            cityHallCount=int(city_hall_count or 0),
            eventCount=event_count,
        )
        return APIResponse(data=data)
    else:
        enrolled_exists = exists(
            select(1).where(
                ActivityEnrollment.activity_id == Activity.id,
                ActivityEnrollment.user_id == current_user.id,
                ActivityEnrollment.status == "joined",
            )
        )
        scope = [
            Activity.activity_kind == EVENT_ACTIVITY_KIND,
            *time_filters,
            or_(Activity.organizer_id == current_user.id, enrolled_exists),
        ]
        total = (await db.execute(select(func.count(Activity.id)).where(*scope))).scalar_one()
        rows = (
            (
                await db.execute(
                    select(Activity)
                    .where(*scope)
                    .order_by(*_my_activities_order(timeScope, now_utc))
                    .offset((page - 1) * pageSize)
                    .limit(pageSize)
                )
            )
            .scalars()
            .all()
        )

    data = MyActivitiesData(
        list=[_my_activity_item(a, now_utc) for a in rows],
        total=int(total or 0),
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

    read_rows = await db.execute(
        select(UserChatRead.activity_id, UserChatRead.last_read_message_id).where(
            UserChatRead.user_id == current_user.id,
            UserChatRead.activity_id.in_(activity_ids),
        )
    )
    read_map = {int(aid): int(last_read or 0) for aid, last_read in read_rows.all()}
    unread_map = await get_chat_unread_counts(
        db, current_user.id, activities, read_map
    )

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
    await reset_chat_unread(current_user.id, activity_pk)
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


def _login_user_from_model(user: User) -> LoginUser:
    return LoginUser(
        userId=f"u_{user.id}",
        nickname=user.nickname,
        avatarUrl=user.avatar_url,
        gender=user.gender,
        status=user.status,
        onboardingCompletedAt=datetime_to_rfc3339_utc_z(user.onboarding_completed_at),
    )


async def _bind_phone_response(db: AsyncSession, user: User, merged: bool) -> APIResponse[BindPhoneData]:
    data = BindPhoneData(
        phoneMasked=_phone_masked(user),
        phoneBound=user_has_phone(user),
        merged=merged,
    )
    if merged:
        settings = get_settings()
        data.accessToken = create_access_token(user.id)
        data.expiresIn = settings.access_token_expires_seconds
        data.refreshToken = await issue_refresh_token(user.id, settings.refresh_token_expires_seconds)
        data.user = _login_user_from_model(user)
    return APIResponse(data=data)


@router.post("/phone/bind-wechat")
async def bind_phone_wechat(
    payload: BindPhoneWechatRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[BindPhoneData]:
    """小程序 ``getPhoneNumber`` 的 code 绑定手机号；若手机号已有短信账号则合并。"""
    if current_user.status != "active":
        raise HTTPException(status_code=403, detail="User is restricted")
    try:
        phone = await get_phone_number_from_code(payload.phoneCode)
    except WechatLoginError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("get_phone_number_from_code failed user_id=%s", current_user.id)
        raise HTTPException(status_code=400, detail="获取微信手机号失败") from exc
    try:
        user, merged = await bind_phone_to_user(db, current_user, phone)
        return await _bind_phone_response(db, user, merged)
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("bind_phone_wechat failed user_id=%s", current_user.id)
        raise HTTPException(status_code=500, detail="绑定手机号失败") from exc


@router.post("/phone/bind-sms")
async def bind_phone_sms(
    payload: BindPhoneSmsRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[BindPhoneData]:
    """短信验证码绑定手机号（微信用户备用）。"""
    if current_user.status != "active":
        raise HTTPException(status_code=403, detail="User is restricted")
    phone = parse_cn_mobile(payload.phone)
    if phone is None:
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    redis_key = f"wm:sms:bind_phone:{phone}"
    cached = await redis_client.get(redis_key)
    if not cached or cached != payload.code:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    await redis_client.delete(redis_key)

    user, merged = await bind_phone_to_user(db, current_user, phone)
    return await _bind_phone_response(db, user, merged)


@router.post("/feedback")
async def create_user_feedback(
    payload: CreateUserFeedbackRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[UserFeedbackCreateData]:
    """提交意见与建议（需登录；用于运营回访与排期）。"""
    if current_user.status != "active":
        raise HTTPException(status_code=403, detail="User is restricted")
    plat = (payload.platform or "mp-weixin").strip()[:16] or "mp-weixin"
    app_ver = (payload.app_version or "").strip()[:32]
    exp = (payload.expectation or "").strip()[:500]
    note = (payload.contact_note or "").strip()[:160]
    row = UserFeedback(
        user_id=current_user.id,
        scene=payload.scene,
        description=payload.description.strip(),
        expectation=exp,
        contact_willing=bool(payload.contact_willing),
        contact_note=note,
        platform=plat,
        app_version=app_ver,
        status="new",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return APIResponse(data=UserFeedbackCreateData(feedbackId=f"fb_{row.id}"))

