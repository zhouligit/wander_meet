from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.activity_message import ActivityMessage
from app.models.user import User
from app.models.user_chat_read import UserChatRead
from app.schemas.common import APIResponse
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

router = APIRouter(prefix="/me", tags=["me"])

EPOCH_UTC = datetime(1970, 1, 1, tzinfo=UTC)


@router.get("/stats")
async def my_stats(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MyStatsData]:
    organized = await db.scalar(
        select(func.count(Activity.id)).where(Activity.organizer_id == current_user.id)
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
    phone_masked = "***********"
    if len(current_user.phone_hash) >= 4:
        phone_masked = f"***{current_user.phone_hash[-4:]}"
    return APIResponse(
        data=MeData(
            userId=f"u_{current_user.id}",
            phoneMasked=phone_masked,
            nickname=current_user.nickname,
            avatarUrl=current_user.avatar_url,
            tags=[],
            status=current_user.status,
            verification=VerificationSummary(status="none", canCreateActivity=True),
        )
    )


@router.patch("")
async def update_me(
    payload: UpdateMeRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MeData]:
    if payload.nickname is not None:
        current_user.nickname = payload.nickname
    if payload.avatarUrl is not None:
        current_user.avatar_url = payload.avatarUrl
    await db.commit()
    await db.refresh(current_user)
    return await get_me(current_user=current_user)


@router.get("/activities")
async def my_activities(
    role: str = Query(..., pattern="^(organized|joined)$"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MyActivitiesData]:
    if role == "organized":
        base_stmt = select(Activity).where(Activity.organizer_id == current_user.id)
        total = (
            await db.execute(
                select(func.count(Activity.id)).where(Activity.organizer_id == current_user.id)
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
                    .order_by(Activity.start_at.desc())
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

        chat_items.append(
            MyChatItem(
                activityId=f"act_{activity.id}",
                title=activity.title,
                activityStatus=activity.activity_status,
                memberCount=int(member_count_map.get(activity.id, 0)),
                lastMessage=last_message,
                lastMessageAt=last_message_at,
                unreadCount=int(unread_map.get(activity.id, 0)),
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

