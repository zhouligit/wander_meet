"""运维：合并重复用户（微信 openid 账号 + 短信手机号账号）。"""

from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_phone
from app.models.user import User
from app.services.phone_validation import parse_cn_mobile
from app.services.user_account_merge import merge_user_into
from app.services.user_phone_bind import user_has_phone

logger = logging.getLogger(__name__)


def _conflicting_phones(a: User, b: User) -> bool:
    if not user_has_phone(a) or not user_has_phone(b):
        return False
    return (a.phone or "").strip() != (b.phone or "").strip()


def _conflicting_mp_openids(a: User, b: User) -> bool:
    oa = (a.mp_openid or "").strip()
    ob = (b.mp_openid or "").strip()
    return bool(oa and ob and oa != ob)


def _backfill_phone_to_target(target: User, source: User) -> None:
    if user_has_phone(target) or not user_has_phone(source):
        return
    phone = (source.phone or "").strip()
    normalized = parse_cn_mobile(phone)
    if normalized is None:
        return
    target.phone = normalized
    target.phone_hash = hash_phone(normalized)


async def admin_merge_users(
    db: AsyncSession,
    *,
    from_user_id: int,
    to_user_id: int,
    note: str | None = None,
) -> User:
    if from_user_id == to_user_id:
        raise HTTPException(status_code=400, detail="fromUserId and toUserId must differ")

    from_user = await db.scalar(select(User).where(User.id == from_user_id))
    to_user = await db.scalar(select(User).where(User.id == to_user_id))
    if not from_user:
        raise HTTPException(status_code=404, detail="fromUser not found")
    if not to_user:
        raise HTTPException(status_code=404, detail="toUser not found")

    if _conflicting_phones(from_user, to_user):
        raise HTTPException(
            status_code=409,
            detail="Both users have different bound phones; resolve manually before merge",
        )
    if _conflicting_mp_openids(from_user, to_user):
        raise HTTPException(
            status_code=409,
            detail="Both users are bound to different WeChat openids",
        )

    _backfill_phone_to_target(to_user, from_user)
    await merge_user_into(db, from_user_id=from_user_id, to_user_id=to_user_id)
    await db.commit()

    kept = await db.scalar(select(User).where(User.id == to_user_id))
    if not kept:
        raise HTTPException(status_code=500, detail="merge failed")

    logger.info(
        "admin_user_merge from_id=%s to_id=%s note=%s",
        from_user_id,
        to_user_id,
        note or "",
    )
    return kept


async def admin_search_users(
    db: AsyncSession,
    *,
    phone: str | None = None,
    mp_openid: str | None = None,
    user_id: int | None = None,
    limit: int = 20,
) -> list[User]:
    filters = []
    if user_id is not None:
        filters.append(User.id == user_id)
    if phone:
        normalized = parse_cn_mobile(phone)
        if normalized is None:
            raise HTTPException(status_code=400, detail="Invalid phone")
        ph = hash_phone(normalized)
        filters.append(or_(User.phone == normalized, User.phone_hash == ph))
    if mp_openid:
        oid = mp_openid.strip()
        if not oid:
            raise HTTPException(status_code=400, detail="mpOpenid is empty")
        filters.append(User.mp_openid == oid)

    if not filters:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of userId, phone, mpOpenid",
        )

    rows = (
        await db.execute(
            select(User).where(or_(*filters)).order_by(User.id.asc()).limit(limit)
        )
    ).scalars().all()
    return list(rows)
