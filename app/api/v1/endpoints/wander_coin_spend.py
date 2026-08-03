"""晃晃币消费 API"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.activity import Activity
from app.models.growth_trust import UserBadge, UserEntitlement
from app.models.user import User
from app.services.wander_coin_service import spend_coins, get_wallet_info

router = APIRouter()


class PinActivityRequest(BaseModel):
    activity_id: int
    hours: int = 24


class PurchaseBadgeRequest(BaseModel):
    badge_code: str  # 如 "social_expert"


class PurchaseAvatarFrameRequest(BaseModel):
    frame_code: str  # 如 "gold_frame"


# ---------------------------------------------------------------------------
# 活动置顶：50 晃晃币
# ---------------------------------------------------------------------------

@router.post("/wander-coin/spend/pin-activity")
async def pin_activity_with_coins(
    request: PinActivityRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """使用晃晃币置顶活动（50 币，置顶 24h）"""
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

    # 2. 扣款
    tx = await spend_coins(
        db=db,
        user_id=current_user.id,
        amount=50,
        tx_type="spend_pin",
        ref_type="activity",
        ref_id=request.activity_id,
        remark=f"活动置顶 {request.hours}h",
    )
    if not tx:
        raise HTTPException(status_code=400, detail="晃晃币余额不足")

    # 3. 设置置顶
    activity.is_pinned = True
    activity.pinned_until = datetime.now() + timedelta(hours=request.hours)
    await db.flush()

    return {
        "code": 0,
        "message": "活动置顶成功",
        "data": {
            "activity_id": request.activity_id,
            "pinned_until": pinned.isoformat() if (pinned := activity.pinned_until) else None,
            "coins_spent": 50,
            "balance_after": tx.balance_after,
        },
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
    """使用晃晃币购买徽章（200 币）"""
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
        amount=200,
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

    return {
        "code": 0,
        "message": "徽章购买成功",
        "data": {
            "badge_code": request.badge_code,
            "badge_id": badge.id,
            "coins_spent": 200,
            "balance_after": tx.balance_after,
        },
    }


# ---------------------------------------------------------------------------
# 头像框购买：300 晃晃币
# ---------------------------------------------------------------------------

@router.post("/wander-coin/spend/avatar-frame")
async def purchase_avatar_frame_with_coins(
    request: PurchaseAvatarFrameRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """使用晃晃币购买头像框（300 币，有效期 30 天）"""
    # 1. 扣款
    tx = await spend_coins(
        db=db,
        user_id=current_user.id,
        amount=300,
        tx_type="spend_avatar_frame",
        ref_type="avatar_frame",
        ref_id=None,
        remark=f"购买头像框: {request.frame_code}",
    )
    if not tx:
        raise HTTPException(status_code=400, detail="晃晃币余额不足")

    # 2. 创建权益记录（复用 UserEntitlement 表）
    now = datetime.now()
    entitlement = UserEntitlement(
        user_id=current_user.id,
        entitlement_type="avatar_frame",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        pin_quota_remaining=0,
        source="coin_purchase",
        source_ref_id=None,
    )
    db.add(entitlement)
    await db.flush()

    return {
        "code": 0,
        "message": "头像框购买成功",
        "data": {
            "frame_code": request.frame_code,
            "entitlement_id": entitlement.id,
            "expires_at": entitlement.expires_at.isoformat(),
            "coins_spent": 300,
            "balance_after": tx.balance_after,
        },
    }
