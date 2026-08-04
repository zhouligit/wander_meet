"""
活动取消时的奖励扣除服务
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.growth_trust import ActivityCheckin, UserTrustProfile
from app.models.trust_level import TrustScoreRecord, UserLevel, PointRecord
from app.models.wander_coin import WanderCoinWallet, WanderCoinTransaction
from app.services import wander_coin_service
from app.services.user_level import add_points
from app.services.trust_score import record_trust_score_change


async def revoke_activity_rewards(
    db: AsyncSession,
    activity: Activity,
    cancel_reason: str | None = None,
) -> dict:
    """
    活动取消时扣除相关奖励
    
    扣除规则：
    - 创建人：扣除发布活动奖励（晃晃币-10, 积分-10）
    - 参与人：扣除报名活动奖励（晃晃币-5, 积分-5）
    - 已打卡参与人：额外扣除打卡奖励（晃晃币-15, 信誉分-10, 积分-15）
    
    所有扣除记录都会写入流水，用户可在列表中查看
    
    Args:
        db: 数据库会话
        activity: 被取消的活动
        cancel_reason: 取消原因（可选）
        
    Returns:
        扣除统计信息
    """
    stats = {
        "organizer": {"coins": 0, "points": 0},
        "participants": {"count": 0, "coins": 0, "points": 0},
        "checkins": {"count": 0, "coins": 0, "trust_score": 0, "points": 0},
    }
    
    reason_prefix = f"活动取消扣除"
    if cancel_reason:
        reason_prefix += f"（{cancel_reason}）"
    
    # 1. 扣除创建人的发布活动奖励
    try:
        # 晃晃币 -10（强制扣除，不受余额限制）
        # 先检查是否已有扣除记录（幂等性）
        from sqlalchemy import select as sa_select
        from app.models.wander_coin import WanderCoinTransaction
        
        existing_deduct = await db.scalar(
            sa_select(WanderCoinTransaction).where(
                WanderCoinTransaction.user_id == activity.organizer_id,
                WanderCoinTransaction.ref_type == "activity",
                WanderCoinTransaction.ref_id == activity.id,
                WanderCoinTransaction.tx_type == "activity_cancel_deduct",
            )
        )
        
        if not existing_deduct:
            # 直接修改余额，不检查余额是否足够
            from app.models.wander_coin import WanderCoinWallet
            result = await db.execute(
                select(WanderCoinWallet).where(WanderCoinWallet.user_id == activity.organizer_id)
            )
            wallet = result.scalar_one_or_none()
            if not wallet:
                wallet = WanderCoinWallet(
                    user_id=activity.organizer_id,
                    balance=0,
                    total_earned=0,
                    total_spent=0,
                )
                db.add(wallet)
                await db.flush()
            
            # 强制扣除（可以为负）
            wallet.balance -= 10
            wallet.total_spent += 10
            
            # 记录流水
            tx = WanderCoinTransaction(
                user_id=activity.organizer_id,
                amount=-10,
                balance_after=wallet.balance,
                tx_type="activity_cancel_deduct",
                ref_type="activity",
                ref_id=activity.id,
                remark=f"{reason_prefix} - 发布活动奖励",
            )
            db.add(tx)
            await db.flush()
            stats["organizer"]["coins"] = 10
        else:
            stats["organizer"]["coins"] = 0  # 已扣除过
        
        # 积分 -10（直接扣除，不检查是否为负）
        from app.models.trust_level import UserLevel, PointRecord
        result = await db.execute(
            select(UserLevel).where(UserLevel.user_id == activity.organizer_id)
        )
        user_level = result.scalar_one_or_none()
        if not user_level:
            user_level = UserLevel(
                user_id=activity.organizer_id,
                total_points=0,
                level_code="recruit",
                level_name="新兵",
            )
            db.add(user_level)
            await db.flush()
        
        points_before = user_level.total_points
        user_level.total_points -= 10
        
        # 记录积分变动
        point_record = PointRecord(
            user_id=activity.organizer_id,
            points=-10,
            points_before=points_before,
            points_after=user_level.total_points,
            reason="activity_cancel_deduct",
            reason_detail=f"{reason_prefix} - 发布活动奖励",
            ref_type="activity",
            ref_id=activity.id,
        )
        db.add(point_record)
        await db.flush()
        stats["organizer"]["points"] = 10
        
    except Exception as e:
        # 记录日志但不中断流程
        import logging
        logging.getLogger(__name__).error(f"扣除创建人 {activity.organizer_id} 奖励失败: {e}", exc_info=True)
    
    # 2. 查询所有参与的报名记录
    enrollments_result = await db.execute(
        select(ActivityEnrollment).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.status == "joined",
        )
    )
    enrollments = enrollments_result.scalars().all()
    
    # 3. 扣除参与人的报名活动奖励
    for enrollment in enrollments:
        if enrollment.user_id == activity.organizer_id:
            # 创建人已在上面扣除
            continue
        
        try:
            # 幂等性检查
            existing_deduct = await db.scalar(
                sa_select(WanderCoinTransaction).where(
                    WanderCoinTransaction.user_id == enrollment.user_id,
                    WanderCoinTransaction.ref_type == "activity",
                    WanderCoinTransaction.ref_id == activity.id,
                    WanderCoinTransaction.tx_type == "activity_cancel_deduct",
                )
            )
            
            if not existing_deduct:
                # 强制扣除晃晃币 - 使用select查询
                result = await db.execute(
                    select(WanderCoinWallet).where(WanderCoinWallet.user_id == enrollment.user_id)
                )
                wallet = result.scalar_one_or_none()
                if not wallet:
                    wallet = WanderCoinWallet(
                        user_id=enrollment.user_id,
                        balance=0,
                        total_earned=0,
                        total_spent=0,
                    )
                    db.add(wallet)
                    await db.flush()
                
                wallet.balance -= 5
                wallet.total_spent += 5
                
                tx = WanderCoinTransaction(
                    user_id=enrollment.user_id,
                    amount=-5,
                    balance_after=wallet.balance,
                    tx_type="activity_cancel_deduct",
                    ref_type="activity",
                    ref_id=activity.id,
                    remark=f"{reason_prefix} - 报名活动奖励",
                )
                db.add(tx)
                await db.flush()
                stats["participants"]["coins"] += 5
            
            # 强制扣除积分
            result = await db.execute(
                select(UserLevel).where(UserLevel.user_id == enrollment.user_id)
            )
            user_level = result.scalar_one_or_none()
            if not user_level:
                user_level = UserLevel(
                    user_id=enrollment.user_id,
                    total_points=0,
                    level_code="recruit",
                    level_name="新兵",
                )
                db.add(user_level)
                await db.flush()
            
            points_before = user_level.total_points
            user_level.total_points -= 5
            
            point_record = PointRecord(
                user_id=enrollment.user_id,
                points=-5,
                points_before=points_before,
                points_after=user_level.total_points,
                reason="activity_cancel_deduct",
                reason_detail=f"{reason_prefix} - 报名活动奖励",
                ref_type="activity",
                ref_id=activity.id,
            )
            db.add(point_record)
            await db.flush()
            stats["participants"]["points"] += 5
            stats["participants"]["count"] += 1
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"扣除参与人 {enrollment.user_id} 奖励失败: {e}", exc_info=True)
    
    # 4. 查询已打卡的参与人，额外扣除打卡奖励
    checkins_result = await db.execute(
        select(ActivityCheckin).where(
            ActivityCheckin.activity_id == activity.id,
        )
    )
    checkins = checkins_result.scalars().all()
    
    for checkin in checkins:
        try:
            # 幂等性检查
            existing_deduct = await db.scalar(
                sa_select(WanderCoinTransaction).where(
                    WanderCoinTransaction.user_id == checkin.user_id,
                    WanderCoinTransaction.ref_type == "activity_checkin",
                    WanderCoinTransaction.ref_id == activity.id,
                    WanderCoinTransaction.tx_type == "activity_cancel_deduct",
                )
            )
            
            if not existing_deduct:
                # 强制扣除晃晃币
                result = await db.execute(
                    select(WanderCoinWallet).where(WanderCoinWallet.user_id == checkin.user_id)
                )
                wallet = result.scalar_one_or_none()
                if not wallet:
                    wallet = WanderCoinWallet(
                        user_id=checkin.user_id,
                        balance=0,
                        total_earned=0,
                        total_spent=0,
                    )
                    db.add(wallet)
                    await db.flush()
                
                wallet.balance -= 15
                wallet.total_spent += 15
                
                tx = WanderCoinTransaction(
                    user_id=checkin.user_id,
                    amount=-15,
                    balance_after=wallet.balance,
                    tx_type="activity_cancel_deduct",
                    ref_type="activity_checkin",
                    ref_id=activity.id,
                    remark=f"{reason_prefix} - 打卡活动奖励",
                )
                db.add(tx)
                await db.flush()
                stats["checkins"]["coins"] += 15
            
            # 强制扣除信誉分
            result = await db.execute(
                select(UserTrustProfile).where(UserTrustProfile.user_id == checkin.user_id)
            )
            user_trust = result.scalar_one_or_none()
            if not user_trust:
                user_trust = UserTrustProfile(
                    user_id=checkin.user_id,
                    trust_score=500,
                )
                db.add(user_trust)
                await db.flush()
            
            trust_before = user_trust.trust_score
            user_trust.trust_score -= 10
            
            trust_record = TrustScoreRecord(
                user_id=checkin.user_id,
                change=-10,
                trust_score_before=trust_before,
                trust_score_after=user_trust.trust_score,
                reason="activity_cancel_deduct",
                reason_detail=f"{reason_prefix} - 打卡活动奖励",
                ref_type="activity_checkin",
                ref_id=activity.id,
            )
            db.add(trust_record)
            await db.flush()
            stats["checkins"]["trust_score"] += 10
            
            # 强制扣除积分
            result = await db.execute(
                select(UserLevel).where(UserLevel.user_id == checkin.user_id)
            )
            user_level = result.scalar_one_or_none()
            if not user_level:
                user_level = UserLevel(
                    user_id=checkin.user_id,
                    total_points=0,
                    level_code="recruit",
                    level_name="新兵",
                )
                db.add(user_level)
                await db.flush()
            
            points_before = user_level.total_points
            user_level.total_points -= 15
            
            point_record = PointRecord(
                user_id=checkin.user_id,
                points=-15,
                points_before=points_before,
                points_after=user_level.total_points,
                reason="activity_cancel_deduct",
                reason_detail=f"{reason_prefix} - 打卡活动奖励",
                ref_type="activity_checkin",
                ref_id=activity.id,
            )
            db.add(point_record)
            await db.flush()
            stats["checkins"]["points"] += 15
            stats["checkins"]["count"] += 1
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"扣除打卡人 {checkin.user_id} 奖励失败: {e}", exc_info=True)
    
    return stats
