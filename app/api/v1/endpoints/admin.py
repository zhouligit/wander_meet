from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user
from app.db.session import get_db_session
from app.models.activity import Activity
from app.models.user import User
from app.schemas.common import APIResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/activities")
async def admin_activities(
    activityStatus: str = Query("pending_review"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_admin_user),
) -> APIResponse[dict]:
    filters = [Activity.activity_status == activityStatus] if activityStatus else []
    total = (await db.execute(select(func.count(Activity.id)).where(*filters))).scalar_one()
    rows = (
        (
            await db.execute(
                select(Activity)
                .where(*filters)
                .order_by(Activity.id.desc())
                .offset((page - 1) * pageSize)
                .limit(pageSize)
            )
        )
        .scalars()
        .all()
    )
    return APIResponse(
        data={
            "list": [
                {
                    "activityId": f"act_{a.id}",
                    "title": a.title,
                    "activityStatus": a.activity_status,
                    "startAt": a.start_at,
                }
                for a in rows
            ],
            "total": total,
            "page": page,
            "pageSize": pageSize,
        }
    )


@router.post("/activities/{activity_id}/approve")
async def admin_approve_activity(
    activity_id: str,
    comment: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_admin_user),
) -> APIResponse[dict]:
    _ = comment
    aid = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == aid))
    if not activity:
        return APIResponse(code=404, message="activity not found", data={"status": "not_found"})
    activity.activity_status = "published"
    await db.commit()
    return APIResponse(data={"activityId": f"act_{aid}", "activityStatus": "published"})


@router.post("/activities/{activity_id}/reject")
async def admin_reject_activity(
    activity_id: str,
    reason: str,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_admin_user),
) -> APIResponse[dict]:
    aid = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == aid))
    if not activity:
        return APIResponse(code=404, message="activity not found", data={"status": "not_found"})
    activity.activity_status = "rejected"
    activity.description = f"{activity.description}\n\n[审核拒绝] {reason}"
    await db.commit()
    return APIResponse(data={"activityId": f"act_{aid}", "activityStatus": "rejected"})


@router.post("/users/{user_id}/ban")
async def admin_ban_user(
    user_id: str,
    reason: str,
    scope: str = "full",
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
) -> APIResponse[dict]:
    _ = reason, scope, admin_user
    uid = _parse_user_id(user_id)
    user = await db.scalar(select(User).where(User.id == uid))
    if not user:
        return APIResponse(code=404, message="user not found", data={"status": "not_found"})
    user.status = "banned"
    await db.commit()
    return APIResponse(data={"userId": f"u_{uid}", "status": "banned"})


@router.post("/users/{user_id}/unban")
async def admin_unban_user(
    user_id: str,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_admin_user),
) -> APIResponse[dict]:
    uid = _parse_user_id(user_id)
    user = await db.scalar(select(User).where(User.id == uid))
    if not user:
        return APIResponse(code=404, message="user not found", data={"status": "not_found"})
    user.status = "active"
    await db.commit()
    return APIResponse(data={"userId": f"u_{uid}", "status": "active", "updatedAt": datetime.now(UTC)})


def _parse_activity_id(activity_id: str) -> int:
    if activity_id.startswith("act_"):
        activity_id = activity_id[4:]
    return int(activity_id)


def _parse_user_id(user_id: str) -> int:
    if user_id.startswith("u_"):
        user_id = user_id[2:]
    return int(user_id)

