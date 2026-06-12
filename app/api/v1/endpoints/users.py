from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.services.user_profile_fields import bio_from_user, tags_from_user
from app.services.growth_trust import build_public_trust_fields
from app.services.dm_relationship import (
    either_blocked,
    get_thread_by_users,
    is_activity_participant,
    user_considers_peer_connected,
)
from app.models.activity import Activity
from app.models.dm_request import DmRequest
from app.models.user import User
from app.models.user_verification import UserVerification
from app.schemas.common import APIResponse
from app.schemas.user_public import UserDmContextData, UserPublicProfileData
from app.schemas.city_group import CityHostBadgeItem
from app.services.city_group_host import list_city_host_badges

router = APIRouter(prefix="/users", tags=["users"])


def _parse_user_id(user_id: str) -> int:
    s = (user_id or "").strip()
    if s.startswith("u_"):
        s = s[2:]
    return int(s)


def _parse_activity_id_query(activity_id: str) -> int:
    s = activity_id[4:] if activity_id.startswith("act_") else activity_id
    if not s.isdigit():
        raise ValueError("bad activity id")
    return int(s)


@router.get("/{user_id}/dm-context")
async def get_user_dm_context(
    user_id: str,
    activity_id: str = Query(..., alias="activityId"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[UserDmContextData]:
    """在给定活动语境下，查询与对方的私聊关系（是否已有线程、待处理申请等）。"""
    try:
        activity_pk = _parse_activity_id_query(activity_id)
    except ValueError:
        return APIResponse(
            code=400,
            message="invalid activity id",
            data=UserDmContextData(canRequest=False, denyReason="invalid_activity"),
        )
    try:
        target_id = _parse_user_id(user_id)
    except ValueError:
        return APIResponse(
            code=400,
            message="invalid user id",
            data=UserDmContextData(canRequest=False, denyReason="invalid_user"),
        )

    if target_id == current_user.id:
        return APIResponse(
            data=UserDmContextData(canRequest=False, denyReason="self"),
        )

    target = await db.scalar(select(User).where(User.id == target_id))
    if not target or target.status != "active":
        return APIResponse(
            code=404,
            message="user not found",
            data=UserDmContextData(canRequest=False, denyReason="not_found"),
        )

    if not await is_activity_participant(db, activity_pk, current_user.id):
        return APIResponse(
            data=UserDmContextData(canRequest=False, denyReason="not_in_activity"),
        )
    if not await is_activity_participant(db, activity_pk, target_id):
        return APIResponse(
            data=UserDmContextData(canRequest=False, denyReason="target_not_in_activity"),
        )

    if await either_blocked(db, current_user.id, target_id):
        return APIResponse(
            data=UserDmContextData(canRequest=False, denyReason="blocked"),
        )

    thread = await get_thread_by_users(db, current_user.id, target_id)
    if thread and await user_considers_peer_connected(db, current_user.id, target_id):
        return APIResponse(
            data=UserDmContextData(
                threadId=f"dmthr_{thread.id}",
                canRequest=False,
                denyReason="has_thread",
            )
        )

    out_req = await db.scalar(
        select(DmRequest).where(
            DmRequest.from_user_id == current_user.id,
            DmRequest.to_user_id == target_id,
            DmRequest.status == "pending",
        )
    )
    if out_req:
        return APIResponse(
            data=UserDmContextData(
                outgoingPendingRequestId=f"dmreq_{out_req.id}",
                canRequest=False,
                denyReason="pending_outgoing",
            )
        )

    in_req = await db.scalar(
        select(DmRequest).where(
            DmRequest.from_user_id == target_id,
            DmRequest.to_user_id == current_user.id,
            DmRequest.status == "pending",
        )
    )
    if in_req:
        return APIResponse(
            data=UserDmContextData(
                incomingPendingRequestId=f"dmreq_{in_req.id}",
                canRequest=False,
                denyReason="pending_incoming",
            )
        )

    from app.services.growth_trust import can_initiate_dm

    if not await can_initiate_dm(db, current_user.id):
        return APIResponse(
            data=UserDmContextData(
                canRequest=False,
                denyReason="low_trust_score",
            )
        )

    return APIResponse(data=UserDmContextData(canRequest=True))


@router.get("/{user_id}/public")
async def get_user_public_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
) -> APIResponse[UserPublicProfileData | None]:
    """查看其他用户公开资料（需登录）。被封禁用户对外返回不存在。"""
    try:
        uid = _parse_user_id(user_id)
    except ValueError:
        return APIResponse(code=404, message="user not found", data=None)

    target = await db.scalar(select(User).where(User.id == uid))
    if not target or target.status != "active":
        return APIResponse(code=404, message="user not found", data=None)

    organized = await db.scalar(
        select(func.count(Activity.id)).where(Activity.organizer_id == uid)
    )

    approved = await db.scalar(
        select(UserVerification).where(
            UserVerification.user_id == uid,
            UserVerification.status == "approved",
        )
    )
    verification_badge = approved is not None

    pub_g = target.gender
    if pub_g is not None and pub_g not in ("male", "female", "unspecified"):
        pub_g = None
    trust_fields = await build_public_trust_fields(db, target)
    host_badges = await list_city_host_badges(db, uid)
    data = UserPublicProfileData(
        userId=f"u_{target.id}",
        nickname=target.nickname,
        avatarUrl=target.avatar_url,
        gender=pub_g,
        bio=bio_from_user(target),
        tags=tags_from_user(target),
        verificationBadge=verification_badge,
        organizedCount=int(organized or 0),
        cityHostBadges=[CityHostBadgeItem(**b) for b in host_badges],
        **trust_fields,
    )
    return APIResponse(data=data)
