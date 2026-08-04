"""
退出活动时的奖励扣除服务
"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.trust_level import UserLevel, PointRecord
from app.models.wander_coin import WanderCoinWallet, WanderCoinTransaction

logger = logging.getLogger(__name__)


async def revoke_enrollment_rewards(
    db: AsyncSession,
    user_id: int,
    activity: Activity,
) -> dict:
    """
    用户退出活动时扣除报名奖励
    
    扣除规则：
    - 晃晃币 -5
    - 积分 -5
    
    Args:
        db: 数据库会话
        user_id: 退出活动的用户ID
        activity: 活动对象
        
    Returns:
        扣除统计信息
    """
    stats = {"coins": 0, "points": 0}
    
    reason_prefix = f"退出活动扣除（{activity.title}）"
    
    try:
        # 1. 幂等性检查 - 是否已扣除过
        existing_deduct = await db.scalar(
            select(WanderCoinTransaction).where(
                WanderCoinTransaction.user_id == user_id,
                WanderCoinTransaction.ref_type == "enrollment_cancel",
                WanderCoinTransaction.ref_id == activity.id,
                WanderCoinTransaction.tx_type == "enrollment_cancel_deduct",
            )
        )
        
        if existing_deduct:
            logger.info(f"用户 {user_id} 退出活动 {activity.id} 的奖励已扣除过")
            return stats
        
        # 2. 扣除晃晃币
        wallet = await db.scalar(
            select(WanderCoinWallet).where(WanderCoinWallet.user_id == user_id)
        )
        
        if not wallet:
            wallet = WanderCoinWallet(
                user_id=user_id,
                balance=0,
                total_earned=0,
                total_spent=0,
            )
            db.add(wallet)
            await db.flush()
        
        wallet.balance -= 5
        wallet.total_spent += 5
        
        tx = WanderCoinTransaction(
            user_id=user_id,
            amount=-5,
            balance_after=wallet.balance,
            tx_type="enrollment_cancel_deduct",
            ref_type="enrollment_cancel",
            ref_id=activity.id,
            remark=reason_prefix,
        )
        db.add(tx)
        await db.flush()
        stats["coins"] = 5
        
        # 3. 扣除积分
        user_level = await db.scalar(
            select(UserLevel).where(UserLevel.user_id == user_id)
        )
        
        if not user_level:
            user_level = UserLevel(
                user_id=user_id,
                total_points=0,
                level_code="recruit",
                level_name="新兵",
            )
            db.add(user_level)
            await db.flush()
        
        points_before = user_level.total_points
        user_level.total_points -= 5
        
        point_record = PointRecord(
            user_id=user_id,
            points=-5,
            points_before=points_before,
            points_after=user_level.total_points,
            reason="enrollment_cancel_deduct",
            reason_detail=reason_prefix,
            ref_type="enrollment_cancel",
            ref_id=activity.id,
        )
        db.add(point_record)
        await db.flush()
        stats["points"] = 5
        
        logger.info(
            f"用户 {user_id} 退出活动 {activity.id}，扣除奖励: "
            f"晃晃币-{stats['coins']}, 积分-{stats['points']}"
        )
        
    except Exception as e:
        logger.error(f"扣除用户 {user_id} 退出活动 {activity.id} 奖励失败: {e}", exc_info=True)
        # 不抛出异常，避免影响退出流程
    
    return stats
