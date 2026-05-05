from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.services.user_profile_fields import bio_from_user, tags_from_user
from app.models.activity import Activity
from app.models.user import User
from app.models.user_verification import UserVerification
from app.schemas.common import APIResponse
from app.schemas.user_public import UserPublicProfileData

router = APIRouter(prefix="/users", tags=["users"])


def _parse_user_id(user_id: str) -> int:
    s = (user_id or "").strip()
    if s.startswith("u_"):
        s = s[2:]
    return int(s)


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

    data = UserPublicProfileData(
        userId=f"u_{target.id}",
        nickname=target.nickname,
        avatarUrl=target.avatar_url,
        bio=bio_from_user(target),
        tags=tags_from_user(target),
        verificationBadge=verification_badge,
        organizedCount=int(organized or 0),
    )
    return APIResponse(data=data)
