from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.me import (
    MeData,
    MyActivitiesData,
    MyActivitiesItem,
    PremiumData,
    UpdateMeRequest,
    VerificationSummary,
)

router = APIRouter(prefix="/me", tags=["me"])


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
        activity_ids_subq = (
            select(ActivityEnrollment.activity_id)
            .where(
                ActivityEnrollment.user_id == current_user.id,
                ActivityEnrollment.status == "joined",
            )
            .subquery()
        )
        total = (
            await db.execute(
                select(func.count(Activity.id)).where(Activity.id.in_(select(activity_ids_subq.c.activity_id)))
            )
        ).scalar_one()
        rows = (
            (
                await db.execute(
                    select(Activity)
                    .where(Activity.id.in_(select(activity_ids_subq.c.activity_id)))
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

