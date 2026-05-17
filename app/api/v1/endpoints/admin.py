from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user
from app.db.session import get_db_session
from app.models.activity import Activity
from app.models.user import User
from app.schemas.admin_user import (
    AdminMergeUsersData,
    AdminMergeUsersRequest,
    AdminUserSearchData,
    build_admin_user_search_item,
    parse_public_user_id,
)
from app.schemas.common import APIResponse
from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z
from app.services.admin_user_merge import admin_merge_users, admin_search_users
from app.services.user_phone_bind import mask_user_phone, user_has_phone

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/activities")
async def admin_activities(
    activityStatus: str = Query("pending_review"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_admin_user),
) -> APIResponse[dict]:
    filters = [
        Activity.activity_kind == "event",
    ]
    if activityStatus:
        filters.append(Activity.activity_status == activityStatus)
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
                    "startAt": datetime_to_rfc3339_utc_z(a.start_at),
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


@router.get("/users/search")
async def admin_search_users_endpoint(
    phone: str | None = Query(None, description="大陆 11 位手机号"),
    mpOpenid: str | None = Query(None, description="小程序 openid 全量"),
    userId: str | None = Query(None, description="公开用户 ID，如 u_123"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_admin_user),
) -> APIResponse[AdminUserSearchData]:
    """运维：按手机号 / openid / userId 检索用户，用于重复账号排查。"""
    uid: int | None = None
    if userId:
        try:
            uid = parse_public_user_id(userId)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid userId") from exc

    rows = await admin_search_users(
        db,
        phone=phone,
        mp_openid=mpOpenid,
        user_id=uid,
        limit=limit,
    )
    return APIResponse(
        data=AdminUserSearchData(list=[build_admin_user_search_item(u) for u in rows])
    )


@router.post("/users/merge")
async def admin_merge_users_endpoint(
    payload: AdminMergeUsersRequest,
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
) -> APIResponse[AdminMergeUsersData]:
    """
    运维：合并重复账号。

    ``fromUserId`` 为被删除的源账号（多为纯微信）；``toUserId`` 为保留的主账号（多为短信手机号账号）。
    """
    try:
        from_id = parse_public_user_id(payload.fromUserId)
        to_id = parse_public_user_id(payload.toUserId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid userId") from exc

    to_before = await db.scalar(select(User).where(User.id == to_id))
    from_before = await db.scalar(select(User).where(User.id == from_id))
    if not to_before or not from_before:
        raise HTTPException(status_code=404, detail="user not found")
    openid_transferred = bool((from_before.mp_openid or "").strip()) and not bool(
        (to_before.mp_openid or "").strip()
    )
    kept = await admin_merge_users(
        db,
        from_user_id=from_id,
        to_user_id=to_id,
        note=payload.note,
    )
    _ = admin_user
    openid_after = (kept.mp_openid or "").strip()
    return APIResponse(
        data=AdminMergeUsersData(
            fromUserId=payload.fromUserId,
            toUserId=payload.toUserId,
            phoneMasked=mask_user_phone(kept),
            phoneBound=user_has_phone(kept),
            mpOpenidTransferred=openid_transferred,
        )
    )


def _parse_activity_id(activity_id: str) -> int:
    if activity_id.startswith("act_"):
        activity_id = activity_id[4:]
    return int(activity_id)


def _parse_user_id(user_id: str) -> int:
    if user_id.startswith("u_"):
        user_id = user_id[2:]
    return int(user_id)

