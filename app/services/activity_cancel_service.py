"""
活动取消时的奖励扣除服务
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.growth_trust import ActivityCheckin
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
        # 晃晃币 -10
        await wander_coin_service.spend_coins(
            db,
            user_id=activity.organizer_id,
            amount=10,
            tx_type="activity_cancel_deduct",
            ref_type="activity",
            ref_id=activity.id,
            remark=f"{reason_prefix} - 发布活动奖励",
        )
        stats["organizer"]["coins"] = 10
        
        # 积分 -10
        await add_points(
            db,
            user_id=activity.organizer_id,
            points=-10,
            reason="activity_cancel_deduct",
            reason_detail=f"{reason_prefix} - 发布活动奖励",
            ref_type="activity",
            ref_id=activity.id,
        )
        stats["organizer"]["points"] = 10
    except Exception as e:
        # 记录日志但不中断流程
        print(f"扣除创建人奖励失败: {e}")
    
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
            # 晃晃币 -5
            await wander_coin_service.spend_coins(
                db,
                user_id=enrollment.user_id,
                amount=5,
                tx_type="activity_cancel_deduct",
                ref_type="activity",
                ref_id=activity.id,
                remark=f"{reason_prefix} - 报名活动奖励",
            )
            stats["participants"]["coins"] += 5
            
            # 积分 -5
            await add_points(
                db,
                user_id=enrollment.user_id,
                points=-5,
                reason="activity_cancel_deduct",
                reason_detail=f"{reason_prefix} - 报名活动奖励",
                ref_type="activity",
                ref_id=activity.id,
            )
            stats["participants"]["points"] += 5
            stats["participants"]["count"] += 1
        except Exception as e:
            print(f"扣除参与人 {enrollment.user_id} 奖励失败: {e}")
    
    # 4. 查询已打卡的参与人，额外扣除打卡奖励
    checkins_result = await db.execute(
        select(ActivityCheckin).where(
            ActivityCheckin.activity_id == activity.id,
        )
    )
    checkins = checkins_result.scalars().all()
    
    for checkin in checkins:
        try:
            # 晃晃币 -15
            await wander_coin_service.spend_coins(
                db,
                user_id=checkin.user_id,
                amount=15,
                tx_type="activity_cancel_deduct",
                ref_type="activity_checkin",
                ref_id=activity.id,
                remark=f"{reason_prefix} - 打卡活动奖励",
            )
            stats["checkins"]["coins"] += 15
            
            # 信誉分 -10
            await record_trust_score_change(
                db,
                user_id=checkin.user_id,
                change=-10,
                reason="activity_cancel_deduct",
                reason_detail=f"{reason_prefix} - 打卡活动奖励",
                ref_type="activity_checkin",
                ref_id=activity.id,
            )
            stats["checkins"]["trust_score"] += 10
            
            # 积分 -15
            await add_points(
                db,
                user_id=checkin.user_id,
                points=-15,
                reason="activity_cancel_deduct",
                reason_detail=f"{reason_prefix} - 打卡活动奖励",
                ref_type="activity_checkin",
                ref_id=activity.id,
            )
            stats["checkins"]["points"] += 15
            stats["checkins"]["count"] += 1
        except Exception as e:
            print(f"扣除打卡人 {checkin.user_id} 奖励失败: {e}")
    
    return stats
