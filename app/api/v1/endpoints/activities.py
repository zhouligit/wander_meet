from datetime import UTC, datetime, timedelta
import math
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.services.user_profile_fields import bio_from_user, tags_from_user
from app.services.activity_query import (
    activity_city_code_matches,
    date_range_start_filters,
    effective_activity_status,
    not_ended_condition,
    to_utc,
    to_utc_optional,
)
from app.services.activity_enroll import enroll_user_in_activity
from app.services.activity_category import normalize_activity_category
from app.services.city_hall import EVENT_ACTIVITY_KIND, is_city_hall_activity
from app.services.contact_content_filter import contact_text_blocked_reason
from app.services.chat_message_payload import build_message_row_content
from app.services.chat_location import message_content_fields
from app.db.session import get_db_session
from app.services.activity_lifecycle import mark_activity_ended
from app.services.chat_unread import increment_chat_unread_for_message
from app.services.user_cache import invalidate_me_stats
from app.services.response_cache import (
    activity_list_cache_key,
    activity_nearby_cache_key,
    get_cached_activity_detail,
    get_cached_activity_list,
    get_cached_activity_nearby,
    invalidate_activity_read_caches,
    set_cached_activity_detail,
    set_cached_activity_list,
    set_cached_activity_nearby,
)
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.activity_message import ActivityMessage
from app.models.user import User
from app.schemas.activity import (
    ActivityMemberItem,
    ActivityMembersData,
    ActivityCard,
    ActivityDetailData,
    ActivityDetailOrganizer,
    ActivityListData,
    NearbyActivityListData,
    NearbySearchCenter,
    ChatMessageItem,
    ChatMessagesData,
    ChatMessageSender,
    CreateActivityRequest,
    EnrollmentData,
    MyEnrollment,
    SendMessageRequest,
    UpdateActivityRequest,
)
from app.schemas.common import APIResponse
from app.schemas.feed import FeedListData, FeedPostCreateData, FeedPostCreateRequest, FeedPostItem
from app.services.feed import create_activity_post, list_activity_posts

router = APIRouter(prefix="/activities", tags=["activities"])
logger = logging.getLogger(__name__)


def _category_label_for_api(activity: Activity) -> str:
    return (activity.category_label or "").strip()


def _organizer_for_detail(org: User | None) -> ActivityDetailOrganizer:
    if not org:
        return ActivityDetailOrganizer(
            userId="u_0",
            nickname="未知组织者",
            avatarUrl=None,
            bio="",
            tags=[],
        )
    return ActivityDetailOrganizer(
        userId=f"u_{org.id}",
        nickname=org.nickname,
        avatarUrl=org.avatar_url,
        bio=bio_from_user(org),
        tags=tags_from_user(org),
    )


@router.get("")
async def list_activities(
    request: Request,
    cityCode: str = Query(...),
    dateRange: str = Query("all"),
    categoryId: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    optional_user: User | None = Depends(get_optional_user),
) -> APIResponse[ActivityListData]:
    if optional_user:
        request.state.user_id = optional_user.id

    now_utc = datetime.now(UTC)
    cc = (cityCode or "").strip()
    if not cc or len(cc) > 16:
        raise HTTPException(status_code=400, detail="invalid cityCode")
    filters = [
        activity_city_code_matches(Activity.city_code, cc),
        Activity.activity_kind == EVENT_ACTIVITY_KIND,
        Activity.activity_status == "published",
        not_ended_condition(now_utc),
    ]
    filters.extend(date_range_start_filters(dateRange))
    if categoryId:
        filters.append(Activity.category_id == categoryId)

    cache_key = activity_list_cache_key(cc, dateRange, categoryId, page, pageSize)
    cached_list = await get_cached_activity_list(cache_key)
    if cached_list is not None:
        cards = list(cached_list.list)
        if optional_user and cards:
            activity_ids = [_parse_activity_id(c.activityId) for c in cards]
            jr = await db.execute(
                select(ActivityEnrollment.activity_id).where(
                    ActivityEnrollment.user_id == optional_user.id,
                    ActivityEnrollment.activity_id.in_(activity_ids),
                    ActivityEnrollment.status == "joined",
                )
            )
            joined_ids = {int(r[0]) for r in jr.all()}
            cards = [
                c.model_copy(
                    update={
                        "enrollmentStatus": "joined" if _parse_activity_id(c.activityId) in joined_ids else None
                    }
                )
                for c in cards
            ]
        return APIResponse(
            data=ActivityListData(
                list=cards,
                total=cached_list.total,
                page=cached_list.page,
                pageSize=cached_list.pageSize,
            )
        )

    total_stmt = select(func.count(Activity.id)).where(*filters)
    total = (await db.execute(total_stmt)).scalar_one()

    base_stmt = select(Activity).where(*filters).order_by(Activity.start_at.asc())
    rows = (
        (
            await db.execute(
                base_stmt.offset((page - 1) * pageSize).limit(pageSize)
            )
        )
        .scalars()
        .all()
    )

    activity_ids = [a.id for a in rows]
    enrollment_map: dict[int, int] = {}
    if activity_ids:
        enrollment_rows = await db.execute(
            select(ActivityEnrollment.activity_id, func.count(ActivityEnrollment.id))
            .where(
                ActivityEnrollment.activity_id.in_(activity_ids),
                ActivityEnrollment.status == "joined",
            )
            .group_by(ActivityEnrollment.activity_id)
        )
        enrollment_map = {aid: count for aid, count in enrollment_rows.all()}

    joined_ids: set[int] = set()
    if optional_user and activity_ids:
        jr = await db.execute(
            select(ActivityEnrollment.activity_id).where(
                ActivityEnrollment.user_id == optional_user.id,
                ActivityEnrollment.activity_id.in_(activity_ids),
                ActivityEnrollment.status == "joined",
            )
        )
        joined_ids = {int(r[0]) for r in jr.all()}

    cards = [
        ActivityCard(
            activityId=f"act_{a.id}",
            title=a.title,
            startAt=a.start_at,
            locationName=a.location_name,
            lat=float(a.lat),
            lng=float(a.lng),
            enrolledCount=enrollment_map.get(a.id, 0),
            maxMembers=a.max_members,
            categoryId=a.category_id,
            categoryLabel=_category_label_for_api(a),
            activityStatus=effective_activity_status(a, now_utc),
            enrollmentStatus="joined" if a.id in joined_ids else None,
        )
        for a in rows
    ]

    list_data = ActivityListData(list=cards, total=total, page=page, pageSize=pageSize)
    await set_cached_activity_list(
        cache_key,
        ActivityListData(
            list=[c.model_copy(update={"enrollmentStatus": None}) for c in cards],
            total=total,
            page=page,
            pageSize=pageSize,
        ),
    )
    return APIResponse(data=list_data)


@router.get("/nearby")
async def list_nearby_activities(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radiusKm: float = Query(5, ge=0.5, le=20),
    cityCode: str | None = Query(None),
    dateRange: str = Query("all"),
    categoryId: str | None = Query(None),
    sortBy: str = Query("distance"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    optional_user: User | None = Depends(get_optional_user),
) -> APIResponse[NearbyActivityListData]:
    if sortBy not in {"distance", "startAt"}:
        raise HTTPException(status_code=400, detail="sortBy must be distance or startAt")
    if optional_user:
        request.state.user_id = optional_user.id

    now_utc = datetime.now(UTC)
    lat_delta = radiusKm / 111.32
    lng_denominator = 111.32 * max(math.cos(math.radians(lat)), 0.0001)
    lng_delta = radiusKm / lng_denominator

    min_lat = lat - lat_delta
    max_lat = lat + lat_delta
    min_lng = lng - lng_delta
    max_lng = lng + lng_delta

    distance_expr = _distance_meters_expr(lat=lat, lng=lng)
    base_filters = [
        Activity.activity_kind == EVENT_ACTIVITY_KIND,
        Activity.activity_status == "published",
        not_ended_condition(now_utc),
        Activity.lat >= min_lat,
        Activity.lat <= max_lat,
        Activity.lng >= min_lng,
        Activity.lng <= max_lng,
    ]
    base_filters.extend(date_range_start_filters(dateRange))
    if cityCode:
        base_filters.append(activity_city_code_matches(Activity.city_code, cityCode))
    if categoryId:
        base_filters.append(Activity.category_id == categoryId)

    nearby_cache_key = activity_nearby_cache_key(
        city_code=cityCode,
        date_range=dateRange,
        category_id=categoryId,
        sort_by=sortBy,
        lat=lat,
        lng=lng,
        radius_km=radiusKm,
        page=page,
        page_size=pageSize,
    )
    cached_nearby = await get_cached_activity_nearby(nearby_cache_key)
    if cached_nearby is not None:
        cards = list(cached_nearby.list)
        if optional_user and cards:
            activity_ids = [_parse_activity_id(c.activityId) for c in cards]
            jr = await db.execute(
                select(ActivityEnrollment.activity_id).where(
                    ActivityEnrollment.user_id == optional_user.id,
                    ActivityEnrollment.activity_id.in_(activity_ids),
                    ActivityEnrollment.status == "joined",
                )
            )
            joined_ids = {int(r[0]) for r in jr.all()}
            cards = [
                c.model_copy(
                    update={
                        "enrollmentStatus": "joined"
                        if _parse_activity_id(c.activityId) in joined_ids
                        else None
                    }
                )
                for c in cards
            ]
        return APIResponse(
            data=NearbyActivityListData(
                list=cards,
                total=cached_nearby.total,
                page=cached_nearby.page,
                pageSize=cached_nearby.pageSize,
                searchCenter=cached_nearby.searchCenter,
                radiusKm=cached_nearby.radiusKm,
            )
        )

    nearby_subq = (
        select(
            Activity.id.label("activity_id"),
            distance_expr.label("distance_meters"),
        )
        .where(*base_filters)
        .subquery()
    )

    distance_limit = radiusKm * 1000
    total_stmt = (
        select(func.count(Activity.id))
        .select_from(Activity)
        .join(nearby_subq, nearby_subq.c.activity_id == Activity.id)
        .where(nearby_subq.c.distance_meters <= distance_limit)
    )
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = (
        select(Activity, nearby_subq.c.distance_meters)
        .join(nearby_subq, nearby_subq.c.activity_id == Activity.id)
        .where(nearby_subq.c.distance_meters <= distance_limit)
    )
    if sortBy == "startAt":
        stmt = stmt.order_by(Activity.start_at.asc(), nearby_subq.c.distance_meters.asc())
    else:
        stmt = stmt.order_by(nearby_subq.c.distance_meters.asc(), Activity.start_at.asc())

    rows = (await db.execute(stmt.offset((page - 1) * pageSize).limit(pageSize))).all()
    activities = [row[0] for row in rows]
    distance_map = {row[0].id: int(round(float(row[1]))) for row in rows}

    activity_ids = [a.id for a in activities]
    enrollment_map: dict[int, int] = {}
    if activity_ids:
        enrollment_rows = await db.execute(
            select(ActivityEnrollment.activity_id, func.count(ActivityEnrollment.id))
            .where(
                ActivityEnrollment.activity_id.in_(activity_ids),
                ActivityEnrollment.status == "joined",
            )
            .group_by(ActivityEnrollment.activity_id)
        )
        enrollment_map = {aid: count for aid, count in enrollment_rows.all()}

    joined_ids: set[int] = set()
    if optional_user and activity_ids:
        jr = await db.execute(
            select(ActivityEnrollment.activity_id).where(
                ActivityEnrollment.user_id == optional_user.id,
                ActivityEnrollment.activity_id.in_(activity_ids),
                ActivityEnrollment.status == "joined",
            )
        )
        joined_ids = {int(r[0]) for r in jr.all()}

    cards = [
        ActivityCard(
            activityId=f"act_{a.id}",
            title=a.title,
            startAt=a.start_at,
            locationName=a.location_name,
            lat=float(a.lat),
            lng=float(a.lng),
            distanceMeters=distance_map.get(a.id),
            enrolledCount=enrollment_map.get(a.id, 0),
            maxMembers=a.max_members,
            categoryId=a.category_id,
            categoryLabel=_category_label_for_api(a),
            activityStatus=effective_activity_status(a, now_utc),
            enrollmentStatus="joined" if a.id in joined_ids else None,
        )
        for a in activities
    ]
    logger.info(
        "nearby_activities user_id=%s request_id=%s city=%s radius_km=%.2f page=%s page_size=%s total=%s returned=%s",
        getattr(request.state, "user_id", None),
        getattr(request.state, "request_id", ""),
        cityCode,
        radiusKm,
        page,
        pageSize,
        total,
        len(cards),
    )

    nearby_data = NearbyActivityListData(
        list=cards,
        total=total,
        page=page,
        pageSize=pageSize,
        searchCenter=NearbySearchCenter(lat=lat, lng=lng),
        radiusKm=radiusKm,
    )
    await set_cached_activity_nearby(
        nearby_cache_key,
        NearbyActivityListData(
            list=[c.model_copy(update={"enrollmentStatus": None}) for c in cards],
            total=total,
            page=page,
            pageSize=pageSize,
            searchCenter=nearby_data.searchCenter,
            radiusKm=radiusKm,
        ),
    )
    return APIResponse(data=nearby_data)


async def _build_activity_detail_data(
    db: AsyncSession,
    activity: Activity,
    current_user: User | None,
    now_utc: datetime,
) -> ActivityDetailData:
    organizer = await db.scalar(select(User).where(User.id == activity.organizer_id))
    enrolled_count = await db.scalar(
        select(func.count(ActivityEnrollment.id)).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.status == "joined",
        )
    )
    my_enrollment_row = None
    if current_user is not None:
        my_enrollment_row = await db.scalar(
            select(ActivityEnrollment).where(
                ActivityEnrollment.activity_id == activity.id,
                ActivityEnrollment.user_id == current_user.id,
                ActivityEnrollment.status == "joined",
            )
        )
    return ActivityDetailData(
        activityId=f"act_{activity.id}",
        activityKind=activity.activity_kind,
        title=activity.title,
        description=activity.description,
        categoryId=activity.category_id,
        categoryLabel=_category_label_for_api(activity),
        startAt=activity.start_at,
        endAt=activity.end_at,
        cityCode=activity.city_code,
        locationName=activity.location_name,
        addressDetail=activity.address_detail,
        lat=float(activity.lat),
        lng=float(activity.lng),
        maxMembers=activity.max_members,
        feeType=activity.fee_type,
        feeAmount=activity.fee_amount_cents,
        activityStatus=effective_activity_status(activity, now_utc),
        organizer=_organizer_for_detail(organizer),
        enrolledCount=int(enrolled_count or 0),
        myEnrollment=MyEnrollment(status="joined") if my_enrollment_row else None,
    )


@router.get("/{activity_id}")
async def get_activity_detail(
    request: Request,
    activity_id: str,
    db: AsyncSession = Depends(get_db_session),
    optional_user: User | None = Depends(get_optional_user),
) -> APIResponse[ActivityDetailData]:
    """活动详情：未登录可浏览（与列表一致）；``myEnrollment`` 仅登录且有报名时返回。"""
    if optional_user:
        request.state.user_id = optional_user.id

    activity_pk = _parse_activity_id(activity_id)
    now_utc = datetime.now(UTC)

    cached_detail = await get_cached_activity_detail(activity_pk)
    if cached_detail is not None:
        my_enrollment = None
        if optional_user:
            my_enrollment_row = await db.scalar(
                select(ActivityEnrollment).where(
                    ActivityEnrollment.activity_id == activity_pk,
                    ActivityEnrollment.user_id == optional_user.id,
                    ActivityEnrollment.status == "joined",
                )
            )
            if my_enrollment_row:
                my_enrollment = MyEnrollment(status="joined")
        return APIResponse(
            data=cached_detail.model_copy(update={"myEnrollment": my_enrollment})
        )

    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    data = await _build_activity_detail_data(db, activity, optional_user, now_utc)
    await set_cached_activity_detail(
        activity_pk,
        data.model_copy(update={"myEnrollment": None}),
    )
    return APIResponse(data=data)


@router.post("")
async def create_activity(
    request: Request,
    payload: CreateActivityRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ActivityDetailData]:
    if current_user.status != "active":
        raise HTTPException(status_code=403, detail="User is restricted")

    start_at_utc = to_utc(payload.startAt)
    end_at_utc = to_utc_optional(payload.endAt)
    if end_at_utc is not None and end_at_utc <= start_at_utc:
        raise HTTPException(status_code=400, detail="endAt must be after startAt")

    earliest = datetime.now(UTC) - timedelta(minutes=5)
    if start_at_utc < earliest:
        raise HTTPException(
            status_code=400,
            detail="startAt must not be before now (5 minute tolerance)",
        )

    cat_id, cat_label = normalize_activity_category(
        payload.categoryId, payload.categoryLabel
    )

    activity = Activity(
        organizer_id=current_user.id,
        title=payload.title,
        description=payload.description,
        category_id=cat_id,
        category_label=cat_label,
        city_code=payload.cityCode,
        location_name=payload.locationName,
        address_detail=payload.addressDetail,
        lat=payload.lat,
        lng=payload.lng,
        start_at=start_at_utc,
        end_at=end_at_utc,
        max_members=payload.maxMembers,
        fee_type=payload.feeType,
        fee_amount_cents=payload.feeAmount,
        activity_status="published",
    )
    db.add(activity)
    await db.flush()
    # 发布者默认占 1 席、已加入（与报名记录一致，便于人数与群聊权限）
    db.add(
        ActivityEnrollment(
            activity_id=activity.id,
            user_id=current_user.id,
            status="joined",
        )
    )
    await db.commit()
    await db.refresh(activity)
    await invalidate_activity_read_caches(
        city_code=activity.city_code, activity_id=activity.id
    )
    await invalidate_me_stats(current_user.id)

    now_create = datetime.now(UTC)
    data = await _build_activity_detail_data(db, activity, current_user, now_create)
    logger.info(
        "create_activity user_id=%s request_id=%s activity_id=%s city=%s category=%s",
        current_user.id,
        getattr(request.state, "request_id", ""),
        activity.id,
        activity.city_code,
        activity.category_id,
    )
    return APIResponse(data=data)


@router.post("/{activity_id}/enrollments")
async def enroll_activity(
    request: Request,
    activity_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[EnrollmentData]:
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    enrollment = await enroll_user_in_activity(db, current_user.id, activity)
    from app.services.growth_trust import grant_pending_referral_rewards, on_qualified_action

    action = "city_hall_join" if is_city_hall_activity(activity) else "event_enroll"
    await on_qualified_action(db, current_user.id, action)
    await grant_pending_referral_rewards(db)
    await invalidate_activity_read_caches(
        city_code=activity.city_code, activity_id=activity.id
    )
    await invalidate_me_stats(current_user.id)

    logger.info(
        "enroll_activity user_id=%s request_id=%s activity_id=%s enrollment_id=%s",
        current_user.id,
        getattr(request.state, "request_id", ""),
        activity.id,
        enrollment.id,
    )
    return APIResponse(
        data=EnrollmentData(enrollmentId=f"enr_{enrollment.id}", status=enrollment.status)
    )


@router.delete("/{activity_id}/enrollments/me")
async def cancel_enrollment(
    activity_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict[str, str]]:
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.organizer_id == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Organizer cannot cancel own enrollment; cancel the activity instead",
        )
    enrollment = await db.scalar(
        select(ActivityEnrollment).where(
            ActivityEnrollment.activity_id == activity_pk,
            ActivityEnrollment.user_id == current_user.id,
            ActivityEnrollment.status == "joined",
        )
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    enrollment.status = "cancelled"
    await db.commit()
    await invalidate_activity_read_caches(
        city_code=activity.city_code, activity_id=activity.id
    )
    await invalidate_me_stats(current_user.id)
    return APIResponse(data={"status": "cancelled"})


@router.get("/{activity_id}/posts")
async def list_activity_posts(
    activity_id: str,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    viewer: User | None = Depends(get_optional_user),
) -> APIResponse[FeedListData]:
    activity_pk = _parse_activity_id(activity_id)
    items, total = await list_activity_posts(
        db,
        activity_pk,
        viewer.id if viewer else None,
        page=page,
        page_size=pageSize,
    )
    return APIResponse(
        data=FeedListData(
            list=[FeedPostItem(**x) for x in items],
            total=total,
            page=page,
            pageSize=pageSize,
        )
    )


@router.post("/{activity_id}/posts")
async def create_activity_post_endpoint(
    activity_id: str,
    payload: FeedPostCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[FeedPostCreateData]:
    activity_pk = _parse_activity_id(activity_id)
    row = await create_activity_post(
        db,
        current_user,
        activity_pk,
        payload.content,
        payload.images,
        location_name=payload.locationName,
        lat=payload.lat,
        lng=payload.lng,
    )
    return APIResponse(data=FeedPostCreateData(postId=f"post_{row.id}"))


def _parse_activity_id(activity_id: str) -> int:
    if activity_id.startswith("act_"):
        activity_id = activity_id[4:]
    if not activity_id.isdigit():
        raise HTTPException(status_code=400, detail="Invalid activity id")
    return int(activity_id)


@router.patch("/{activity_id}")
async def update_activity(
    request: Request,
    activity_id: str,
    payload: UpdateActivityRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ActivityDetailData]:
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if is_city_hall_activity(activity):
        raise HTTPException(status_code=400, detail="City hall cannot be modified here")
    if activity.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only organizer can update activity")

    updates = payload.model_dump(exclude_unset=True)
    if "endAt" in updates and "startAt" in updates and to_utc(updates["endAt"]) <= to_utc(
        updates["startAt"]
    ):
        raise HTTPException(status_code=400, detail="endAt must be after startAt")
    if "endAt" in updates and "startAt" not in updates and to_utc(updates["endAt"]) <= to_utc(
        activity.start_at
    ):
        raise HTTPException(status_code=400, detail="endAt must be after startAt")

    if "categoryId" in updates or "categoryLabel" in updates:
        new_cid = updates.get("categoryId", activity.category_id)
        new_label = updates.get("categoryLabel", activity.category_label)
        cat_id, cat_label = normalize_activity_category(new_cid, new_label)
        activity.category_id = cat_id
        activity.category_label = cat_label
        updates.pop("categoryId", None)
        updates.pop("categoryLabel", None)

    field_map = {
        "title": "title",
        "description": "description",
        "startAt": "start_at",
        "endAt": "end_at",
        "locationName": "location_name",
        "addressDetail": "address_detail",
        "lat": "lat",
        "lng": "lng",
        "maxMembers": "max_members",
        "feeType": "fee_type",
        "feeAmount": "fee_amount_cents",
    }
    for req_key, model_key in field_map.items():
        if req_key in updates:
            val = updates[req_key]
            if req_key == "startAt":
                val = to_utc(val)
            elif req_key == "endAt" and val is not None:
                val = to_utc(val)
            setattr(activity, model_key, val)
    await db.commit()
    await db.refresh(activity)
    await invalidate_activity_read_caches(
        city_code=activity.city_code, activity_id=activity.id
    )

    return await get_activity_detail(
        request=request,
        activity_id=f"act_{activity.id}",
        db=db,
        optional_user=current_user,
    )


@router.post("/{activity_id}/cancel")
async def cancel_activity(
    request: Request,
    activity_id: str,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict[str, str]]:
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if is_city_hall_activity(activity):
        raise HTTPException(status_code=400, detail="City hall cannot be cancelled here")
    if activity.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only organizer can cancel activity")
    if activity.activity_status in {"cancelled", "ended"}:
        raise HTTPException(status_code=400, detail="Activity already closed")

    mark_activity_ended(activity, status="cancelled")
    if reason:
        activity.description = f"{activity.description}\n\n[取消原因] {reason}"
    await db.commit()
    await invalidate_activity_read_caches(
        city_code=activity.city_code, activity_id=activity.id
    )
    await invalidate_me_stats(current_user.id)
    logger.info(
        "cancel_activity user_id=%s request_id=%s activity_id=%s reason=%s",
        current_user.id,
        getattr(request.state, "request_id", ""),
        activity.id,
        bool(reason),
    )

    return APIResponse(
        data={
            "activityId": f"act_{activity.id}",
            "activityStatus": activity.activity_status,
        }
    )


@router.get("/{activity_id}/members")
async def activity_members(
    activity_id: str,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ActivityMembersData]:
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    is_member = await db.scalar(
        select(ActivityEnrollment).where(
            ActivityEnrollment.activity_id == activity_pk,
            ActivityEnrollment.user_id == current_user.id,
            ActivityEnrollment.status == "joined",
        )
    )
    if activity.organizer_id != current_user.id and not is_member:
        raise HTTPException(status_code=403, detail="Only members can view")

    city_hall = is_city_hall_activity(activity)
    member_stmt = (
        select(ActivityEnrollment, User)
        .join(User, User.id == ActivityEnrollment.user_id)
        .where(
            ActivityEnrollment.activity_id == activity_pk,
            ActivityEnrollment.status == "joined",
        )
        .order_by(ActivityEnrollment.created_at.asc())
    )
    if not city_hall:
        member_stmt = member_stmt.where(ActivityEnrollment.user_id != activity.organizer_id)

    members_query = await db.execute(
        member_stmt.offset((page - 1) * pageSize).limit(pageSize)
    )
    members = [
        ActivityMemberItem(
            userId=f"u_{u.id}",
            nickname=u.nickname,
            avatarUrl=u.avatar_url,
            role="member",
            joinedAt=en.created_at,
        )
        for en, u in members_query.all()
    ]
    if not city_hall and page == 1:
        organizer = await db.scalar(select(User).where(User.id == activity.organizer_id))
        if organizer:
            members.insert(
                0,
                ActivityMemberItem(
                    userId=f"u_{organizer.id}",
                    nickname=organizer.nickname,
                    avatarUrl=organizer.avatar_url,
                    role="organizer",
                    joinedAt=activity.created_at,
                ),
            )
    return APIResponse(data=ActivityMembersData(list=members))


@router.get("/{activity_id}/messages")
async def get_messages(
    activity_id: str,
    cursor: str | None = Query(None),
    after: str | None = Query(None, alias="afterMessageId"),
    limit: int = Query(20, ge=1, le=50),
    direction: str = Query("older"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ChatMessagesData]:
    """活动群聊消息。

    - 默认（无 ``cursor`` / ``after``）：最近 ``limit`` 条，时间正序返回。
    - ``afterMessageId``：仅返回该消息 id **之后**的新消息（轮询增量）。
    - ``cursor``：返回该 id **之前**的更旧消息（上拉历史，与 ``after`` 互斥时 ``after`` 优先）。
    """
    activity_pk = _parse_activity_id(activity_id)
    await _assert_member_or_organizer(activity_pk, current_user.id, db)
    _ = direction

    base = (
        select(ActivityMessage, User)
        .join(User, User.id == ActivityMessage.sender_id)
        .where(ActivityMessage.activity_id == activity_pk)
    )

    if after:
        after_id = _parse_message_cursor(after)
        stmt = (
            base.where(ActivityMessage.id > after_id)
            .order_by(ActivityMessage.id.asc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
    elif cursor:
        cursor_id = _parse_message_cursor(cursor)
        stmt = (
            base.where(ActivityMessage.id < cursor_id)
            .order_by(ActivityMessage.id.desc())
            .limit(limit)
        )
        rows = list(reversed((await db.execute(stmt)).all()))
    else:
        stmt = base.order_by(ActivityMessage.id.desc()).limit(limit)
        rows = list(reversed((await db.execute(stmt)).all()))

    items = [
        ChatMessageItem(
            messageId=f"msg_{msg.id}",
            activityId=f"act_{activity_pk}",
            sender=ChatMessageSender(
                userId=f"u_{user.id}",
                nickname=user.nickname,
                avatarUrl=user.avatar_url,
            ),
            msgType=msg.msg_type,
            **message_content_fields(msg.msg_type, msg.text_content, msg.image_url),
            createdAt=msg.created_at,
        )
        for msg, user in rows
    ]
    next_cursor = f"msg_{rows[-1][0].id}" if rows else None
    return APIResponse(data=ChatMessagesData(list=items, nextCursor=next_cursor))


@router.post("/{activity_id}/messages")
async def send_message(
    activity_id: str,
    payload: SendMessageRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ChatMessageItem]:
    activity_pk = _parse_activity_id(activity_id)
    await _assert_member_or_organizer(activity_pk, current_user.id, db)

    msg_type, text_content, image_url = build_message_row_content(payload, current_user.id)

    message = ActivityMessage(
        activity_id=activity_pk,
        sender_id=current_user.id,
        msg_type=msg_type,
        text_content=text_content,
        image_url=image_url,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if activity:
        await increment_chat_unread_for_message(db, activity, current_user.id)

    return APIResponse(
        data=ChatMessageItem(
            messageId=f"msg_{message.id}",
            activityId=f"act_{activity_pk}",
            sender=ChatMessageSender(
                userId=f"u_{current_user.id}",
                nickname=current_user.nickname,
                avatarUrl=current_user.avatar_url,
            ),
            msgType=message.msg_type,
            **message_content_fields(message.msg_type, message.text_content, message.image_url),
            createdAt=message.created_at or datetime.now(UTC),
        )
    )


def _parse_message_cursor(cursor: str) -> int:
    if cursor.startswith("msg_"):
        cursor = cursor[4:]
    if not cursor.isdigit():
        raise HTTPException(status_code=400, detail="Invalid cursor")
    return int(cursor)


async def _assert_member_or_organizer(
    activity_id: int, user_id: int, db: AsyncSession
) -> None:
    activity = await db.scalar(select(Activity).where(Activity.id == activity_id))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.organizer_id == user_id:
        return
    enrollment = await db.scalar(
        select(ActivityEnrollment).where(
            ActivityEnrollment.activity_id == activity_id,
            ActivityEnrollment.user_id == user_id,
            ActivityEnrollment.status == "joined",
        )
    )
    if not enrollment:
        raise HTTPException(status_code=403, detail="Only members can access activity chat")


def _distance_meters_expr(lat: float, lng: float):
    lat_col = cast(Activity.lat, Float)
    lng_col = cast(Activity.lng, Float)
    dlat = func.radians((lat_col - lat) / 2)
    dlng = func.radians((lng_col - lng) / 2)
    a = func.pow(func.sin(dlat), 2) + func.cos(func.radians(lat)) * func.cos(
        func.radians(lat_col)
    ) * func.pow(func.sin(dlng), 2)
    return 6371000 * 2 * func.asin(func.sqrt(a))

