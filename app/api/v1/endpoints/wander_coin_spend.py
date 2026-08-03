"""晃晃币消费 API — 活动置顶 / 徽章购买 / 头像框购买"""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.activity import Activity
from app.models.growth_trust import UserBadge, UserEntitlement
from app.models.user import User
from app.schemas.wander_coin import (
    AvatarFramePurchaseData,
    BadgePurchaseData,
    PinActivityData,
    PinActivityRequest,
    PurchaseAvatarFrameRequest,
    PurchaseBadgeRequest,
)
from app.services.wander_coin_service import spend_coins

router = APIRouter(tags=["wander-coin-spend"])

# ---------------------------------------------------------------------------
# 定价常量
# ---------------------------------------------------------------------------
PIN_ACTIVITY_COINS = 50
BADGE_COINS = 200
AVATAR_FRAME_COINS = 300


# ---------------------------------------------------------------------------
# 活动置顶：50 晃晃币
# ---------------------------------------------------------------------------

@router.post("/wander-coin/spend/pin-activity")
async def pin_activity_with_coins(
    request: PinActivityRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """使用晃晃币置顶活动（50 币，默认 24h）"""
    # 1. 校验活动归属
    result = await db.execute(
        select(Activity).where(
            Activity.id == request.activity_id,
            Activity.organizer_id == current_user.id,
        )
    )
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在或无权限")

    # 2. 扣款（内部 SELECT FOR UPDATE 保证并发安全）
    tx = await spend_coins(
        db=db,
        user_id=current_user.id,
        amount=PIN_ACTIVITY_COINS,
        tx_type="spend_pin",
        ref_type="activity",
        ref_id=request.activity_id,
        remark=f"活动置顶 {request.hours}h",
    )
    if not tx:
        raise HTTPException(status_code=400, detail="晃晃币余额不足")

    # 3. 设置置顶
    now = datetime.now(UTC)
    pinned_until = now + timedelta(hours=request.hours)
    activity.is_pinned = True
    activity.pinned_until = pinned_until
    await db.commit()

    return {
        "code": 0,
        "message": "活动置顶成功",
        "data": PinActivityData(
            activity_id=request.activity_id,
            pinned_until=pinned_until.isoformat(),
            coins_spent=PIN_ACTIVITY_COINS,
            balance_after=tx.balance_after,
        ).model_dump(),
    }


# ---------------------------------------------------------------------------
# 徽章购买：200 晃晃币
# ---------------------------------------------------------------------------

@router.post("/wander-coin/spend/badge")
async def purchase_badge_with_coins(
    request: PurchaseBadgeRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """使用晃晃币购买永久徽章（200 币）"""
    # 1. 检查是否已拥有
    existing = await db.execute(
        select(UserBadge).where(
            UserBadge.user_id == current_user.id,
            UserBadge.badge_id == request.badge_code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="已拥有该徽章")

    # 2. 扣款
    tx = await spend_coins(
        db=db,
        user_id=current_user.id,
        amount=BADGE_COINS,
        tx_type="spend_badge",
        ref_type="badge",
        ref_id=None,
        remark=f"购买徽章: {request.badge_code}",
    )
    if not tx:
        raise HTTPException(status_code=400, detail="晃晃币余额不足")

    # 3. 创建徽章记录
    badge = UserBadge(
        user_id=current_user.id,
        badge_id=request.badge_code,
        visible=True,
    )
    db.add(badge)
    await db.flush()
    await db.commit()

    return {
        "code": 0,
        "message": "徽章购买成功",
        "data": BadgePurchaseData(
            badge_code=request.badge_code,
            badge_id=badge.id,
            coins_spent=BADGE_COINS,
            balance_after=tx.balance_after,
        ).model_dump(),
    }


# ---------------------------------------------------------------------------
# 头像框购买：300 晃晃币（30 天有效期）
# ---------------------------------------------------------------------------

@router.post("/wander-coin/spend/avatar-frame")
async def purchase_avatar_frame_with_coins(
    request: PurchaseAvatarFrameRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """使用晃晃币购买头像框（300 币，30 天有效期）"""
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=30)

    # 1. 扣款
    tx = await spend_coins(
        db=db,
        user_id=current_user.id,
        amount=AVATAR_FRAME_COINS,
        tx_type="spend_avatar_frame",
        ref_type="avatar_frame",
        ref_id=None,
        remark=f"购买头像框: {request.frame_code}",
    )
    if not tx:
        raise HTTPException(status_code=400, detail="晃晃币余额不足")

    # 2. 创建权益记录（复用 UserEntitlement，frame_code 存入 source 扩展字段）
    entitlement = UserEntitlement(
        user_id=current_user.id,
        entitlement_type=f"avatar_frame:{request.frame_code}",
        starts_at=now,
        expires_at=expires_at,
        pin_quota_remaining=0,
        source="coin_purchase",
        source_ref_id=None,
    )
    db.add(entitlement)
    await db.flush()
    await db.commit()

    return {
        "code": 0,
        "message": "头像框购买成功",
        "data": AvatarFramePurchaseData(
            frame_code=request.frame_code,
            entitlement_id=entitlement.id,
            expires_at=expires_at.isoformat(),
            coins_spent=AVATAR_FRAME_COINS,
            balance_after=tx.balance_after,
        ).model_dump(),
    }
