from datetime import UTC, datetime, timedelta
import math
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.core.config import get_settings
from app.services.user_profile_fields import bio_from_user, tags_from_user
from app.services.activity_query import (
    HOME_ACTIVITY_WINDOW_DAYS,
    activity_city_code_matches,
    date_range_start_filters,
    effective_activity_status,
    enrollment_count_subquery,
    not_ended_condition,
    to_utc,
    to_utc_optional,
)
from app.services.activity_share_qrcode import get_activity_share_qrcode_base64
from app.services.activity_enroll import enroll_user_in_activity
from app.services.enrollment_identity import (
    apply_enrollment_identity,
    build_my_enrollment,
    can_edit_enrollment_identity,
    enrollment_roster_item,
    member_identity_for_organizer,
    normalize_enroll_identity_payload,
)
from app.services.activity_category import category_display_name, normalize_activity_category
from app.services.city_hall import EVENT_ACTIVITY_KIND, is_city_hall_activity
from app.services.city_group_host import (
    build_host_role_map,
    city_code_for_activity,
    get_active_hosts,
    is_user_muted_in_city,
)
from app.services.content_moderation import assert_text_fields_safe, moderate_send_message_request
from app.services.user_phone_bind import assert_user_phone_bound
from app.services.user_profile import assert_user_profile_complete
from app.services.wechat_content_security import SCENE_FORUM, SCENE_SOCIAL
from app.services.chat_chain_signup import (
    add_or_update_entry,
    close_chain,
    remove_entry,
)
from app.services.chat_mentions import build_validated_text_content
from app.services.chat_message_payload import build_message_row_content
from app.services.chat_location import message_content_fields
from app.services.bos_storage import resolve_bos_read_url
from app.db.session import get_db_session
from app.services.activity_lifecycle import mark_activity_ended
from app.services.activity_update import (
    activity_has_started,
    apply_activity_update,
    post_organizer_chat_notice,
)
from app.services.activity_guide import (
    apply_activity_guide_sections,
    guide_fields_for_api,
)
from app.services.activity_images import (
    activity_image_fields_for_api,
    apply_activity_images,
    maybe_expire_pending_activity_images,
    public_cover_image_url,
)
from app.services.chat_unread import enrich_activity_cards_chat_stats, increment_chat_unread_for_message
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
    EnrollActivityRequest,
    EnrollmentData,
    EnrollmentRosterData,
    ActivityShareQrcodeData,
    MyEnrollment,
    CancelActivityRequest,
    ChainSignupEntryRequest,
    SendMessageRequest,
    UpdateActivityRequest,
    UpdateEnrollmentIdentityRequest,
)
from app.schemas.common import APIResponse
from app.schemas.feed import FeedListData, FeedPostCreateData, FeedPostCreateRequest, FeedPostItem
from app.services.feed import create_activity_post, list_activity_posts as list_activity_posts_svc

router = APIRouter(prefix="/activities", tags=["activities"])
logger = logging.getLogger(__name__)


def _category_fields_for_api(activity: Activity) -> dict[str, str]:
    sub = (activity.sub_category_id or "").strip()
    label = (activity.category_label or "").strip()
    return {
        "categoryId": activity.category_id,
        "subCategoryId": sub,
        "categoryLabel": label,
        "categoryDisplay": category_display_name(
            activity.category_id, activity.sub_category_id, activity.category_label
        ),
    }


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
        avatarUrl=resolve_bos_read_url(org.avatar_url),
        bio=bio_from_user(org),
        tags=tags_from_user(org),
    )


@router.get("")
async def list_activities(
    request: Request,
    cityCode: str = Query(...),
    dateRange: str = Query("all"),
    categoryId: str | None = Query(None),
    subCategoryId: str | None = Query(None),
    sortBy: str = Query("startAt"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    optional_user: User | None = Depends(get_optional_user),
) -> APIResponse[ActivityListData]:
    if sortBy not in {"startAt", "popularity"}:
        raise HTTPException(status_code=400, detail="sortBy must be startAt or popularity")
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
    filters.extend(date_range_start_filters(dateRange, now_utc=now_utc))
    if categoryId:
        filters.append(Activity.category_id == categoryId)
    if subCategoryId:
        filters.append(Activity.sub_category_id == subCategoryId)

    cache_key = activity_list_cache_key(cc, dateRange, categoryId, page, pageSize, sortBy)
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
        uid = optional_user.id if optional_user else None
        cards = await enrich_activity_cards_chat_stats(db, uid, cards)
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

    base_stmt = select(Activity).where(*filters)
    if sortBy == "popularity":
        enroll_cnt = enrollment_count_subquery()
        base_stmt = base_stmt.order_by(enroll_cnt.desc(), Activity.start_at.asc())
    else:
        base_stmt = base_stmt.order_by(Activity.start_at.asc())
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
            **_category_fields_for_api(a),
            activityStatus=effective_activity_status(a, now_utc),
            enrollmentStatus="joined" if a.id in joined_ids else None,
            coverImageUrl=public_cover_image_url(a),
        )
        for a in rows
    ]

    uid = optional_user.id if optional_user else None
    cards = await enrich_activity_cards_chat_stats(db, uid, cards)

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
    subCategoryId: str | None = Query(None),
    sortBy: str = Query("distance"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    optional_user: User | None = Depends(get_optional_user),
) -> APIResponse[NearbyActivityListData]:
    if sortBy not in {"distance", "startAt", "popularity"}:
        raise HTTPException(status_code=400, detail="sortBy must be distance, startAt, or popularity")
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
    base_filters.extend(date_range_start_filters(dateRange, now_utc=now_utc))
    if cityCode:
        base_filters.append(activity_city_code_matches(Activity.city_code, cityCode))
    if categoryId:
        base_filters.append(Activity.category_id == categoryId)
    if subCategoryId:
        base_filters.append(Activity.sub_category_id == subCategoryId)

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
        uid = optional_user.id if optional_user else None
        cards = await enrich_activity_cards_chat_stats(db, uid, cards)
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
    elif sortBy == "popularity":
        enroll_cnt = enrollment_count_subquery()
        stmt = stmt.order_by(enroll_cnt.desc(), nearby_subq.c.distance_meters.asc(), Activity.start_at.asc())
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
            **_category_fields_for_api(a),
            activityStatus=effective_activity_status(a, now_utc),
            enrollmentStatus="joined" if a.id in joined_ids else None,
            coverImageUrl=public_cover_image_url(a),
        )
        for a in activities
    ]
    uid = optional_user.id if optional_user else None
    cards = await enrich_activity_cards_chat_stats(db, uid, cards)
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
        **_category_fields_for_api(activity),
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
        myEnrollment=build_my_enrollment(my_enrollment_row, activity, now_utc),
        requireEnrollmentIdentity=bool(activity.require_enrollment_identity),
        isOrganizer=current_user is not None and activity.organizer_id == current_user.id,
        **activity_image_fields_for_api(
            activity, current_user.id if current_user else None
        ),
        **guide_fields_for_api(activity, int(enrolled_count or 0)),
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
        activity_row = await db.scalar(select(Activity).where(Activity.id == activity_pk))
        if activity_row:
            if await maybe_expire_pending_activity_images(db, activity_row):
                await db.commit()
                await db.refresh(activity_row)
            cached_detail = cached_detail.model_copy(
                update={
                    **activity_image_fields_for_api(
                        activity_row, optional_user.id if optional_user else None
                    ),
                    **guide_fields_for_api(
                        activity_row, int(cached_detail.enrolledCount or 0)
                    ),
                    "isOrganizer": optional_user is not None
                    and activity_row.organizer_id == optional_user.id,
                    "requireEnrollmentIdentity": bool(
                        activity_row.require_enrollment_identity
                    ),
                }
            )
        my_enrollment = None
        if optional_user and activity_row:
            my_enrollment_row = await db.scalar(
                select(ActivityEnrollment).where(
                    ActivityEnrollment.activity_id == activity_pk,
                    ActivityEnrollment.user_id == optional_user.id,
                    ActivityEnrollment.status == "joined",
                )
            )
            if my_enrollment_row:
                my_enrollment = build_my_enrollment(
                    my_enrollment_row, activity_row, now_utc
                )
        return APIResponse(
            data=cached_detail.model_copy(update={"myEnrollment": my_enrollment})
        )

    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    if await maybe_expire_pending_activity_images(db, activity):
        await db.commit()
        await db.refresh(activity)

    data = await _build_activity_detail_data(db, activity, optional_user, now_utc)
    await set_cached_activity_detail(
        activity_pk,
        data.model_copy(
            update={
                "myEnrollment": None,
                "isOrganizer": False,
                **activity_image_fields_for_api(activity, None),
            }
        ),
    )
    return APIResponse(data=data)


@router.get("/{activity_id}/share-qrcode")
async def get_activity_share_qrcode(
    activity_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> APIResponse[ActivityShareQrcodeData]:
    """活动详情分享：生成微信小程序码（扫码进入活动详情页）。"""
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if is_city_hall_activity(activity):
        raise HTTPException(status_code=400, detail="城市大群不支持活动分享码")
    if activity.activity_kind != EVENT_ACTIVITY_KIND:
        raise HTTPException(status_code=400, detail="仅普通活动可生成分享码")
    if activity.activity_status == "cancelled":
        raise HTTPException(status_code=400, detail="活动已取消，无法生成分享码")

    scene, image_base64 = await get_activity_share_qrcode_base64(activity_pk)
    settings = get_settings()
    landing = (
        settings.wx_mp_share_qrcode_page or "pages/activity-detail/activity-detail"
    ).strip().lstrip("/")
    return APIResponse(
        data=ActivityShareQrcodeData(
            activityId=f"act_{activity.id}",
            title=(activity.title or "").strip(),
            scene=scene,
            imageBase64=image_base64,
            landingPage=landing,
        )
    )


@router.post("")
async def create_activity(
    request: Request,
    payload: CreateActivityRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ActivityDetailData]:
    if current_user.status != "active":
        raise HTTPException(status_code=403, detail="User is restricted")
    assert_user_profile_complete(current_user)
    assert_user_phone_bound(current_user)

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
    latest = datetime.now(UTC) + timedelta(days=HOME_ACTIVITY_WINDOW_DAYS)
    if start_at_utc > latest:
        raise HTTPException(
            status_code=400,
            detail="开始时间需在7天内：首页只展示近7天可参加的活动，方便大家近期组局见面",
        )

    cat_id, sub_id, cat_label = normalize_activity_category(
        payload.categoryId, payload.subCategoryId, payload.categoryLabel
    )

    await assert_text_fields_safe(
        current_user,
        {
            "title": payload.title,
            "description": payload.description or "",
            "locationName": payload.locationName,
            "addressDetail": payload.addressDetail or "",
        },
        scene=SCENE_FORUM,
    )

    activity = Activity(
        organizer_id=current_user.id,
        title=payload.title,
        description=payload.description,
        category_id=cat_id,
        sub_category_id=sub_id,
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
        require_enrollment_identity=bool(payload.requireEnrollmentIdentity),
    )
    db.add(activity)
    await db.flush()
    db.add(
        ActivityEnrollment(
            activity_id=activity.id,
            user_id=current_user.id,
            status="joined",
        )
    )
    if payload.images:
        await apply_activity_images(db, activity, current_user, payload.images)
    if payload.guideSections is not None:
        await apply_activity_guide_sections(activity, current_user, payload.guideSections)
    
    # 三体系联动：发布活动奖励
    from app.services.linkage_service import on_activity_publish
    await on_activity_publish(db, current_user.id, activity.id, activity.title)
    
    # T5: 发布首个出游活动 → 晃晃币+100
    from app.services.wander_coin_service import grant_coins
    
    # 检查是否是首个活动
    activity_count = await db.execute(
        select(func.count(Activity.id)).where(
            Activity.organizer_id == current_user.id
        )
    )
    if activity_count.scalar() == 1:  # 刚创建的是第一个
        await grant_coins(
            db=db,
            user_id=current_user.id,
            amount=100,
            tx_type="newbie_task",
            ref_type="task",
            ref_id=5,  # T5
            remark="新人任务T5: 发布首个出游活动",
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
    payload: EnrollActivityRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[EnrollmentData]:
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    assert_user_profile_complete(current_user)
    assert_user_phone_bound(current_user)

    body = payload or EnrollActivityRequest()
    enrollment = await enroll_user_in_activity(
        db,
        current_user.id,
        activity,
        current_user,
        participant_name=body.participantName,
        id_card_number=body.idCardNumber,
    )
    from app.services.growth_trust import grant_pending_referral_rewards, on_qualified_action

    action = "city_hall_join" if is_city_hall_activity(activity) else "event_enroll"
    await on_qualified_action(db, current_user.id, action)
    await grant_pending_referral_rewards(db)
    
    # 三体系联动：报名活动奖励
    from app.services.linkage_service import on_activity_join
    await on_activity_join(db, current_user.id, activity.id)
    
    # T3: 报名首个出游活动 → 晃晃币+50
    from app.services.wander_coin_service import grant_coins
    
    # 检查是否是首个报名（排除自己组织的活动）
    enrollment_count = await db.execute(
        select(func.count(ActivityEnrollment.id))
        .join(Activity, ActivityEnrollment.activity_id == Activity.id)
        .where(
            ActivityEnrollment.user_id == current_user.id,
            Activity.organizer_id != current_user.id,  # 排除自己组织的
        )
    )
    if enrollment_count.scalar() == 1:  # 刚报名的是第一个
        await grant_coins(
            db=db,
            user_id=current_user.id,
            amount=50,
            tx_type="newbie_task",
            ref_type="task",
            ref_id=3,  # T3
            remark="新人任务T3: 报名首个出游活动",
        )
    
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

    # 扣除报名奖励（晃晃币-5, 积分-5）
    from app.services.enrollment_cancel_service import revoke_enrollment_rewards
    await revoke_enrollment_rewards(db, current_user.id, activity)

    enrollment.status = "cancelled"
    await db.commit()
    await invalidate_activity_read_caches(
        city_code=activity.city_code, activity_id=activity.id
    )
    await invalidate_me_stats(current_user.id)
    return APIResponse(data={"status": "cancelled"})


@router.patch("/{activity_id}/enrollments/me/identity")
async def update_my_enrollment_identity(
    activity_id: str,
    payload: UpdateEnrollmentIdentityRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MyEnrollment]:
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if not activity.require_enrollment_identity:
        raise HTTPException(status_code=400, detail="该活动未开启实名报名")
    assert_user_phone_bound(current_user)
    now_utc = datetime.now(UTC)
    if not can_edit_enrollment_identity(activity, now_utc):
        raise HTTPException(status_code=400, detail="活动已开始，无法修改报名信息")

    enrollment = await db.scalar(
        select(ActivityEnrollment).where(
            ActivityEnrollment.activity_id == activity_pk,
            ActivityEnrollment.user_id == current_user.id,
            ActivityEnrollment.status == "joined",
        )
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    name, id_card = normalize_enroll_identity_payload(
        payload.participantName,
        payload.idCardNumber,
        required=True,
    )
    apply_enrollment_identity(enrollment, current_user, name, id_card)
    await db.commit()
    await db.refresh(enrollment)
    await invalidate_activity_read_caches(
        city_code=activity.city_code, activity_id=activity.id
    )
    my_enrollment = build_my_enrollment(enrollment, activity, now_utc)
    if my_enrollment is None:
        raise HTTPException(status_code=500, detail="Enrollment state error")
    return APIResponse(data=my_enrollment)


@router.get("/{activity_id}/enrollments/roster")
async def export_enrollment_roster(
    activity_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[EnrollmentRosterData]:
    """发起人导出完整报名名单（购险等），仅含未脱敏三要素。"""
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only organizer can export roster")
    if not activity.require_enrollment_identity:
        raise HTTPException(status_code=400, detail="该活动未开启实名报名")

    rows = await db.execute(
        select(ActivityEnrollment)
        .where(
            ActivityEnrollment.activity_id == activity_pk,
            ActivityEnrollment.status == "joined",
            ActivityEnrollment.user_id != activity.organizer_id,
        )
        .order_by(ActivityEnrollment.created_at.asc())
    )
    roster: list = []
    for en in rows.scalars().all():
        item = enrollment_roster_item(en)
        if item is not None:
            roster.append(item)
    return APIResponse(
        data=EnrollmentRosterData(activityTitle=activity.title or "", list=roster)
    )


@router.get("/{activity_id}/posts")
async def list_activity_posts(
    activity_id: str,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    viewer: User | None = Depends(get_optional_user),
) -> APIResponse[FeedListData]:
    activity_pk = _parse_activity_id(activity_id)
    items, total = await list_activity_posts_svc(
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
    images = updates.pop("images", None)
    guide_sections = updates.pop("guideSections", None)
    now_utc = datetime.now(UTC)
    if images is not None:
        if activity_has_started(activity, now_utc):
            raise HTTPException(status_code=400, detail="活动进行中不可修改图片")
        await apply_activity_images(db, activity, current_user, images)
    if guide_sections is not None:
        status = effective_activity_status(activity, now_utc)
        if status in {"cancelled", "ended"}:
            raise HTTPException(status_code=400, detail="活动已结束或已取消，无法修改说明")
        await apply_activity_guide_sections(activity, current_user, guide_sections)
    if updates:
        await apply_activity_update(db, activity, current_user, updates, now_utc=now_utc)
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
    payload: CancelActivityRequest = Body(default_factory=CancelActivityRequest),
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

    reason = (payload.reason or "").strip() or None
    if reason:
        await assert_text_fields_safe(current_user, {"reason": reason}, scene=SCENE_FORUM)

    mark_activity_ended(activity, status="cancelled")
    if reason:
        activity.description = f"{activity.description}\n\n[取消原因] {reason}"

    # 活动取消时扣除相关奖励（创建人 + 参与人 + 打卡人）
    from app.services.activity_cancel_service import revoke_activity_rewards
    revoke_stats = await revoke_activity_rewards(db, activity, reason)

    notice = "【活动取消】发起人已取消本次活动"
    if reason:
        notice += f"\n原因：{reason}"
    await post_organizer_chat_notice(db, activity, current_user.id, notice)

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
    q: str | None = Query(None, max_length=32),
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

    show_identity = (
        bool(activity.require_enrollment_identity)
        and activity.organizer_id == current_user.id
    )
    city_hall = is_city_hall_activity(activity)
    q_norm = (q or "").strip()
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
    if q_norm:
        member_stmt = member_stmt.where(User.nickname.ilike(f"%{q_norm}%"))

    members_query = await db.execute(
        member_stmt.offset((page - 1) * pageSize).limit(pageSize)
    )
    members = [
        ActivityMemberItem(
            userId=f"u_{u.id}",
            nickname=u.nickname,
            avatarUrl=resolve_bos_read_url(u.avatar_url),
            role="member",
            joinedAt=en.created_at,
            identity=member_identity_for_organizer(en, show=show_identity),
        )
        for en, u in members_query.all()
    ]
    seen_ids = {m.userId for m in members}

    if city_hall and page == 1:
        cc = await city_code_for_activity(db, activity)
        if cc:
            host_rows = await get_active_hosts(db, cc)
            host_items: list[ActivityMemberItem] = []
            for host, user in host_rows:
                if q_norm and q_norm not in (user.nickname or ""):
                    continue
                uid = f"u_{user.id}"
                if uid in seen_ids:
                    continue
                host_items.append(
                    ActivityMemberItem(
                        userId=uid,
                        nickname=user.nickname,
                        avatarUrl=resolve_bos_read_url(user.avatar_url),
                        role=host.role,
                        joinedAt=host.appointed_at,
                    )
                )
            members = host_items + members
    elif not city_hall and page == 1:
        organizer = await db.scalar(select(User).where(User.id == activity.organizer_id))
        if organizer:
            uid = f"u_{organizer.id}"
            if (not q_norm or q_norm in (organizer.nickname or "")) and uid not in seen_ids:
                members.insert(
                    0,
                    ActivityMemberItem(
                        userId=uid,
                        nickname=organizer.nickname,
                        avatarUrl=resolve_bos_read_url(organizer.avatar_url),
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
    assert_user_profile_complete(current_user)
    assert_user_phone_bound(current_user)
    await _assert_member_or_organizer(activity_pk, current_user.id, db)
    _ = direction

    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    host_role_map: dict[int, str] = {}
    if activity and is_city_hall_activity(activity):
        cc = await city_code_for_activity(db, activity)
        if cc:
            host_role_map = await build_host_role_map(db, cc)

    base = (
        select(ActivityMessage, User)
        .join(User, User.id == ActivityMessage.sender_id)
        .where(
            ActivityMessage.activity_id == activity_pk,
            ActivityMessage.deleted_at.is_(None),
        )
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
                avatarUrl=resolve_bos_read_url(user.avatar_url),
            ),
            msgType=msg.msg_type,
            **message_content_fields(msg.msg_type, msg.text_content, msg.image_url),
            createdAt=msg.created_at,
            senderHostRole=host_role_map.get(user.id),
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
    assert_user_profile_complete(current_user)
    assert_user_phone_bound(current_user)
    await _assert_member_or_organizer(activity_pk, current_user.id, db)

    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    city_hall_strict = bool(activity and is_city_hall_activity(activity))
    if activity and city_hall_strict:
        cc = await city_code_for_activity(db, activity)
        if cc and await is_user_muted_in_city(db, cc, current_user.id):
            raise HTTPException(status_code=403, detail="You are muted in this city group")

    await moderate_send_message_request(current_user, payload, strict=city_hall_strict)
    msg_type, text_content, image_url = build_message_row_content(
        payload, current_user.id, nickname=current_user.nickname
    )
    if msg_type == "text" and payload.mentions:
        text_content = await build_validated_text_content(
            db,
            activity_id=activity_pk,
            text=payload.text or "",
            mentions=payload.mentions,
            strict=city_hall_strict,
        )

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
                avatarUrl=resolve_bos_read_url(current_user.avatar_url),
            ),
            msgType=message.msg_type,
            **message_content_fields(message.msg_type, message.text_content, message.image_url),
            createdAt=message.created_at or datetime.now(UTC),
        )
    )


async def _chain_message_or_404(
    db: AsyncSession, activity_pk: int, message_id: str
) -> ActivityMessage:
    msg_pk = _parse_message_cursor(message_id)
    message = await db.scalar(
        select(ActivityMessage).where(
            ActivityMessage.id == msg_pk,
            ActivityMessage.activity_id == activity_pk,
            ActivityMessage.deleted_at.is_(None),
        )
    )
    if not message or message.msg_type != "chain_signup":
        raise HTTPException(status_code=404, detail="Chain signup message not found")
    return message


def _chat_message_item(
    msg: ActivityMessage,
    user: User,
    activity_pk: int,
    host_role_map: dict[int, str] | None = None,
) -> ChatMessageItem:
    return ChatMessageItem(
        messageId=f"msg_{msg.id}",
        activityId=f"act_{activity_pk}",
        sender=ChatMessageSender(
            userId=f"u_{user.id}",
            nickname=user.nickname,
            avatarUrl=resolve_bos_read_url(user.avatar_url),
        ),
        msgType=msg.msg_type,
        **message_content_fields(msg.msg_type, msg.text_content, msg.image_url),
        createdAt=msg.created_at or datetime.now(UTC),
        senderHostRole=(host_role_map or {}).get(user.id),
    )


async def _host_role_map_for_activity(db: AsyncSession, activity: Activity | None) -> dict[int, str]:
    if not activity or not is_city_hall_activity(activity):
        return {}
    cc = await city_code_for_activity(db, activity)
    if not cc:
        return {}
    return await build_host_role_map(db, cc)


@router.post("/{activity_id}/messages/{message_id}/chain/entries")
async def chain_signup_join(
    activity_id: str,
    message_id: str,
    payload: ChainSignupEntryRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ChatMessageItem]:
    activity_pk = _parse_activity_id(activity_id)
    assert_user_profile_complete(current_user)
    assert_user_phone_bound(current_user)
    await _assert_member_or_organizer(activity_pk, current_user.id, db)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    city_hall_strict = bool(activity and is_city_hall_activity(activity))
    if activity and city_hall_strict:
        cc = await city_code_for_activity(db, activity)
        if cc and await is_user_muted_in_city(db, cc, current_user.id):
            raise HTTPException(status_code=403, detail="You are muted in this city group")

    await assert_text_fields_safe(
        current_user,
        {"note": payload.note},
        scene=SCENE_SOCIAL,
        strict=city_hall_strict,
    )

    message = await _chain_message_or_404(db, activity_pk, message_id)
    message.text_content = add_or_update_entry(
        message.text_content,
        user_id=current_user.id,
        nickname=current_user.nickname,
        note=payload.note or "",
    )
    await db.commit()
    await db.refresh(message)

    sender = await db.scalar(select(User).where(User.id == message.sender_id))
    if not sender:
        raise HTTPException(status_code=500, detail="Sender not found")
    host_role_map = await _host_role_map_for_activity(db, activity)
    return APIResponse(data=_chat_message_item(message, sender, activity_pk, host_role_map))


@router.delete("/{activity_id}/messages/{message_id}/chain/entries/me")
async def chain_signup_leave(
    activity_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ChatMessageItem]:
    activity_pk = _parse_activity_id(activity_id)
    assert_user_profile_complete(current_user)
    assert_user_phone_bound(current_user)
    await _assert_member_or_organizer(activity_pk, current_user.id, db)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))

    message = await _chain_message_or_404(db, activity_pk, message_id)
    message.text_content = remove_entry(message.text_content, user_id=current_user.id)
    await db.commit()
    await db.refresh(message)

    sender = await db.scalar(select(User).where(User.id == message.sender_id))
    if not sender:
        raise HTTPException(status_code=500, detail="Sender not found")
    host_role_map = await _host_role_map_for_activity(db, activity)
    return APIResponse(data=_chat_message_item(message, sender, activity_pk, host_role_map))


@router.post("/{activity_id}/messages/{message_id}/chain/close")
async def chain_signup_close(
    activity_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ChatMessageItem]:
    activity_pk = _parse_activity_id(activity_id)
    assert_user_profile_complete(current_user)
    assert_user_phone_bound(current_user)
    await _assert_member_or_organizer(activity_pk, current_user.id, db)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))

    message = await _chain_message_or_404(db, activity_pk, message_id)
    if message.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only chain creator can close")

    message.text_content = close_chain(message.text_content)
    await db.commit()
    await db.refresh(message)

    sender = await db.scalar(select(User).where(User.id == message.sender_id))
    if not sender:
        raise HTTPException(status_code=500, detail="Sender not found")
    host_role_map = await _host_role_map_for_activity(db, activity)
    return APIResponse(data=_chat_message_item(message, sender, activity_pk, host_role_map))


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

