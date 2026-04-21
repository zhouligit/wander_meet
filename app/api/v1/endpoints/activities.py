from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
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

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("")
async def list_activities(
    cityCode: str = Query(...),
    dateRange: str = Query("all"),
    categoryId: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> APIResponse[ActivityListData]:
    filters = [Activity.city_code == cityCode, Activity.activity_status == "published"]
    if categoryId:
        filters.append(Activity.category_id == categoryId)
    # v0.1: dateRange reserved, currently relies on startAt sorting.
    _ = dateRange

    base_stmt = select(Activity).where(*filters)
    total_stmt = select(func.count(Activity.id)).where(*filters)

    total = (await db.execute(total_stmt)).scalar_one()
    rows = (
        (
            await db.execute(
                base_stmt.order_by(Activity.start_at.asc())
                .offset((page - 1) * pageSize)
                .limit(pageSize)
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
            activityStatus=a.activity_status,
        )
        for a in rows
    ]

    return APIResponse(
        data=ActivityListData(list=cards, total=total, page=page, pageSize=pageSize)
    )


@router.get("/{activity_id}")
async def get_activity_detail(
    activity_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ActivityDetailData]:
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    organizer = await db.scalar(select(User).where(User.id == activity.organizer_id))
    enrolled_count = await db.scalar(
        select(func.count(ActivityEnrollment.id)).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.status == "joined",
        )
    )
    my_enrollment_row = await db.scalar(
        select(ActivityEnrollment).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.user_id == current_user.id,
            ActivityEnrollment.status == "joined",
        )
    )

    data = ActivityDetailData(
        activityId=f"act_{activity.id}",
        title=activity.title,
        description=activity.description,
        categoryId=activity.category_id,
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
        activityStatus=activity.activity_status,
        organizer=ActivityDetailOrganizer(
            userId=f"u_{organizer.id}" if organizer else "u_0",
            nickname=organizer.nickname if organizer else "未知组织者",
            avatarUrl=organizer.avatar_url if organizer else None,
        ),
        enrolledCount=int(enrolled_count or 0),
        myEnrollment=MyEnrollment(status="joined") if my_enrollment_row else None,
    )
    return APIResponse(data=data)


@router.post("")
async def create_activity(
    payload: CreateActivityRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ActivityDetailData]:
    if current_user.status != "active":
        raise HTTPException(status_code=403, detail="User is restricted")
    if payload.endAt and payload.endAt <= payload.startAt:
        raise HTTPException(status_code=400, detail="endAt must be after startAt")

    activity = Activity(
        organizer_id=current_user.id,
        title=payload.title,
        description=payload.description,
        category_id=payload.categoryId,
        city_code=payload.cityCode,
        location_name=payload.locationName,
        address_detail=payload.addressDetail,
        lat=payload.lat,
        lng=payload.lng,
        start_at=payload.startAt,
        end_at=payload.endAt,
        max_members=payload.maxMembers,
        fee_type=payload.feeType,
        fee_amount_cents=payload.feeAmount,
        activity_status="published",
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)

    data = ActivityDetailData(
        activityId=f"act_{activity.id}",
        title=activity.title,
        description=activity.description,
        categoryId=activity.category_id,
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
        activityStatus=activity.activity_status,
        organizer=ActivityDetailOrganizer(
            userId=f"u_{current_user.id}",
            nickname=current_user.nickname,
            avatarUrl=current_user.avatar_url,
        ),
        enrolledCount=0,
        myEnrollment=None,
    )
    return APIResponse(data=data)


@router.post("/{activity_id}/enrollments")
async def enroll_activity(
    activity_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[EnrollmentData]:
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.activity_status != "published":
        raise HTTPException(status_code=400, detail="Activity is not open for enrollment")

    joined_count = await db.scalar(
        select(func.count(ActivityEnrollment.id)).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.status == "joined",
        )
    )
    if int(joined_count or 0) >= activity.max_members:
        raise HTTPException(status_code=409, detail="Activity is full")

    existing = await db.scalar(
        select(ActivityEnrollment).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.user_id == current_user.id,
        )
    )
    if existing:
        if existing.status == "joined":
            raise HTTPException(status_code=409, detail="Already enrolled")
        # Re-join after a previous cancellation (idempotent re-enroll behavior).
        existing.status = "joined"
        await db.commit()
        await db.refresh(existing)
        enrollment = existing
    else:
        enrollment = ActivityEnrollment(
            activity_id=activity.id,
            user_id=current_user.id,
            status="joined",
        )
        db.add(enrollment)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(status_code=409, detail="Already enrolled") from exc
        await db.refresh(enrollment)

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
    return APIResponse(data={"status": "cancelled"})


def _parse_activity_id(activity_id: str) -> int:
    if activity_id.startswith("act_"):
        activity_id = activity_id[4:]
    if not activity_id.isdigit():
        raise HTTPException(status_code=400, detail="Invalid activity id")
    return int(activity_id)


@router.patch("/{activity_id}")
async def update_activity(
    activity_id: str,
    payload: UpdateActivityRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ActivityDetailData]:
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only organizer can update activity")

    updates = payload.model_dump(exclude_unset=True)
    if "endAt" in updates and "startAt" in updates and updates["endAt"] <= updates["startAt"]:
        raise HTTPException(status_code=400, detail="endAt must be after startAt")
    if "endAt" in updates and "startAt" not in updates and updates["endAt"] <= activity.start_at:
        raise HTTPException(status_code=400, detail="endAt must be after startAt")

    field_map = {
        "title": "title",
        "description": "description",
        "categoryId": "category_id",
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
            setattr(activity, model_key, updates[req_key])
    await db.commit()
    await db.refresh(activity)

    return await get_activity_detail(
        activity_id=f"act_{activity.id}", db=db, current_user=current_user
    )


@router.post("/{activity_id}/cancel")
async def cancel_activity(
    activity_id: str,
    reason: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict[str, str]]:
    activity_pk = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == activity_pk))
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only organizer can cancel activity")
    if activity.activity_status in {"cancelled", "ended"}:
        raise HTTPException(status_code=400, detail="Activity already closed")

    activity.activity_status = "cancelled"
    if reason:
        activity.description = f"{activity.description}\n\n[取消原因] {reason}"
    await db.commit()

    return APIResponse(
        data={
            "activityId": f"act_{activity.id}",
            "activityStatus": activity.activity_status,
        }
    )


@router.get("/{activity_id}/members")
async def activity_members(
    activity_id: str,
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

    members_query = await db.execute(
        select(ActivityEnrollment, User)
        .join(User, User.id == ActivityEnrollment.user_id)
        .where(
            ActivityEnrollment.activity_id == activity_pk,
            ActivityEnrollment.status == "joined",
        )
        .order_by(ActivityEnrollment.created_at.asc())
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
    limit: int = Query(20, ge=1, le=50),
    direction: str = Query("older"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ChatMessagesData]:
    activity_pk = _parse_activity_id(activity_id)
    await _assert_member_or_organizer(activity_pk, current_user.id, db)
    _ = direction

    stmt = (
        select(ActivityMessage, User)
        .join(User, User.id == ActivityMessage.sender_id)
        .where(ActivityMessage.activity_id == activity_pk)
    )
    if cursor:
        cursor_id = _parse_message_cursor(cursor)
        stmt = stmt.where(ActivityMessage.id < cursor_id)
    stmt = stmt.order_by(ActivityMessage.id.desc()).limit(limit)
    rows = (await db.execute(stmt)).all()

    rows = list(reversed(rows))
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
            text=msg.text_content,
            imageUrl=msg.image_url,
            createdAt=msg.created_at,
        )
        for msg, user in rows
    ]
    next_cursor = f"msg_{rows[0][0].id}" if rows else None
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

    if payload.msgType not in {"text", "image"}:
        raise HTTPException(status_code=400, detail="Unsupported msgType")
    if payload.msgType == "text" and not payload.text:
        raise HTTPException(status_code=400, detail="text is required for text message")
    if payload.msgType == "image" and not payload.imageUrl:
        raise HTTPException(status_code=400, detail="imageUrl is required for image message")

    message = ActivityMessage(
        activity_id=activity_pk,
        sender_id=current_user.id,
        msg_type=payload.msgType,
        text_content=payload.text if payload.msgType == "text" else None,
        image_url=payload.imageUrl if payload.msgType == "image" else None,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

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
            text=message.text_content,
            imageUrl=message.image_url,
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

