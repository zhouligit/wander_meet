"""绑定手机号：微信快速验证 / 短信验证码；与已有手机号账号自动合并。"""

from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_phone
from app.models.user import User
from app.services.phone_validation import parse_cn_mobile
from app.services.user_account_merge import merge_user_into
from app.services.user_cache import invalidate_user_cache, load_user_for_update

logger = logging.getLogger(__name__)


def user_has_phone(user: User) -> bool:
    p = (user.phone or "").strip()
    return bool(p and len(p) >= 11)


def mask_user_phone(user: User) -> str:
    if not user_has_phone(user):
        return ""
    p = user.phone
    if p and len(p) >= 11:
        return f"{p[:3]}****{p[-4:]}"
    return "***********"


async def bind_phone_to_user(
    db: AsyncSession,
    current_user: User,
    phone: str,
) -> tuple[User, bool]:
    """
  绑定手机号到当前用户。

  返回 ``(生效用户, merged)``。若合并到已有短信账号，``merged=True`` 且返回目标用户。
    """
    normalized = parse_cn_mobile(phone)
    if normalized is None:
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    if user_has_phone(current_user) and current_user.phone == normalized:
        return current_user, False

    user = await load_user_for_update(db, current_user.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    target_hash = hash_phone(normalized)
    existing = await db.scalar(select(User).where(User.phone_hash == target_hash))

    if existing and existing.id == user.id:
        user.phone = normalized
        await db.commit()
        await db.refresh(user)
        await invalidate_user_cache(user.id)
        return user, False

    if existing and existing.id != current_user.id:
        cur_oid = (current_user.mp_openid or "").strip()
        exist_oid = (existing.mp_openid or "").strip()
        # 仅当「双方都是微信账号且 openid 不同」时拒绝；H5 邮箱号无 openid 可并入该手机号账号
        if exist_oid and cur_oid and exist_oid != cur_oid:
            raise HTTPException(
                status_code=409,
                detail="该手机号已绑定其他微信，请使用对应方式登录",
            )
        from_id = current_user.id
        to_id = existing.id
        if not existing.phone:
            existing.phone = normalized
        try:
            await merge_user_into(db, from_user_id=from_id, to_user_id=to_id)
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            logger.exception("bind_phone merge IntegrityError from=%s to=%s", from_id, to_id)
            raise HTTPException(
                status_code=409,
                detail="账号合并失败，请联系客服处理",
            ) from exc
        except ValueError as exc:
            await db.rollback()
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        merged_user = await db.scalar(select(User).where(User.id == to_id))
        if not merged_user:
            raise HTTPException(status_code=500, detail="merge failed")
        await invalidate_user_cache(from_id)
        await invalidate_user_cache(to_id)
        return merged_user, True

    # 无冲突：当前用户（多为纯微信账号）写入真实手机号
    user.phone = normalized
    user.phone_hash = target_hash
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.exception("bind_phone phone_hash conflict user_id=%s", user.id)
        raise HTTPException(
            status_code=409,
            detail="该手机号已被其他账号使用",
        ) from exc
    await db.refresh(user)
    await invalidate_user_cache(user.id)
    return user, False
