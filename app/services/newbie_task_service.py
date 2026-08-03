"""新人任务奖励服务"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.wander_coin import WanderCoinTransaction
from app.services.wander_coin_service import grant_coins
from app.services.trust_score import record_trust_score_change

# 任务 ID 定义
TASK_T1_PROFILE = 1      # 完善资料
TASK_T2_COMMENT = 2      # 首条评论
TASK_T3_ENROLL = 3       # 首个报名
TASK_T4_INVITE_ENROLL = 4 # 邀请报名
TASK_T5_PUBLISH = 5      # 首个发布


async def is_task_completed(db: AsyncSession, user_id: int, task_id: int) -> bool:
    """检查任务是否已完成（通过检查晃晃币发放记录）"""
    stmt = select(func.count(WanderCoinTransaction.id)).where(
        WanderCoinTransaction.user_id == user_id,
        WanderCoinTransaction.ref_type == "newbie_task",
        WanderCoinTransaction.ref_id == task_id
    )
    count = await db.scalar(stmt)
    return count > 0 if count else False


async def grant_task_reward(db: AsyncSession, user_id: int, task_id: int):
    """发放任务奖励（带幂等性）"""
    if await is_task_completed(db, user_id, task_id):
        return

    if task_id == TASK_T1_PROFILE:
        # T1: 完善资料 -> 信誉分+30, 晃晃币+10
        await record_trust_score_change(
            db, user_id, 30,
            reason="newbie_task",
            reason_detail="完善个人资料",
            ref_type="newbie_task",
            ref_id=task_id
        )
        await grant_coins(
            db, user_id, 10,
            tx_type="newbie_task",
            ref_type="newbie_task",
            ref_id=task_id,
            remark="完善个人资料"
        )
    elif task_id == TASK_T2_COMMENT:
        # T2: 首条评论 -> 晃晃币+5
        await grant_coins(
            db, user_id, 5,
            tx_type="newbie_task",
            ref_type="newbie_task",
            ref_id=task_id,
            remark="发布首条评论"
        )
    elif task_id == TASK_T3_ENROLL:
        # T3: 首个报名 -> 晃晃币+50
        await grant_coins(
            db, user_id, 50,
            tx_type="newbie_task",
            ref_type="newbie_task",
            ref_id=task_id,
            remark="报名首个出游活动"
        )
    elif task_id == TASK_T4_INVITE_ENROLL:
        # T4: 邀请报名 -> 晃晃币+30
        await grant_coins(
            db, user_id, 30,
            tx_type="newbie_task",
            ref_type="newbie_task",
            ref_id=task_id,
            remark="邀请好友报名活动"
        )
    elif task_id == TASK_T5_PUBLISH:
        # T5: 首个发布 -> 晃晃币+100
        await grant_coins(
            db, user_id, 100,
            tx_type="newbie_task",
            ref_type="newbie_task",
            ref_id=task_id,
            remark="发布首个出游活动"
        )
