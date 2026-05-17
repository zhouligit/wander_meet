"""绑定手机号：微信快速验证 / 短信验证码；与已有手机号账号自动合并。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_phone
from app.models.user import User
from app.services.phone_validation import parse_cn_mobile
from app.services.user_account_merge import merge_user_into


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

    target_hash = hash_phone(normalized)
    existing = await db.scalar(select(User).where(User.phone_hash == target_hash))

    if existing and existing.id == current_user.id:
        current_user.phone = normalized
        await db.commit()
        await db.refresh(current_user)
        return current_user, False

    if existing and existing.id != current_user.id:
        if existing.mp_openid and existing.mp_openid != current_user.mp_openid:
            raise HTTPException(
                status_code=409,
                detail="该手机号已绑定其他微信，请使用对应方式登录",
            )
        from_id = current_user.id
        to_id = existing.id
        if not existing.phone:
            existing.phone = normalized
        await merge_user_into(db, from_user_id=from_id, to_user_id=to_id)
        await db.commit()
        merged_user = await db.scalar(select(User).where(User.id == to_id))
        if not merged_user:
            raise HTTPException(status_code=500, detail="merge failed")
        return merged_user, True

    # 无冲突：当前用户（多为纯微信账号）写入真实手机号
    current_user.phone = normalized
    current_user.phone_hash = target_hash
    await db.commit()
    await db.refresh(current_user)
    return current_user, False
