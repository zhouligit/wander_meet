"""
退出活动时的奖励扣除服务

支持多轮「报名 → 取消 → 再报名」：
- 以「是否仍存在未扣回的报名发放流水」作为是否扣除的依据
- 不再用「该活动是否曾有过取消扣除流水」做终身幂等（否则第二轮起会漏扣白嫖）
"""
import logging

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.trust_level import PointRecord, UserLevel
from app.models.wander_coin import WanderCoinTransaction
from app.services.wander_coin_service import get_or_create_wallet

logger = logging.getLogger(__name__)

# 与 linkage_service.on_activity_join 保持一致
JOIN_COIN_TX_TYPE = "activity_reward"
JOIN_COIN_REF_TYPE = "activity_join"
JOIN_COIN_REF_TYPE_LEGACY = "activity"
JOIN_COIN_REMARK = "报名活动奖励"
JOIN_POINT_REASON = "join_activity"
JOIN_POINT_DETAIL = "报名活动"
JOIN_POINT_REF_TYPE = "activity_join"
JOIN_POINT_REF_TYPE_LEGACY = "activity"

CANCEL_COIN_TX_TYPE = "enrollment_cancel_deduct"
CANCEL_COIN_REF_TYPE = "enrollment_cancel"
CANCEL_POINT_REASON = "enrollment_cancel_deduct"


async def _find_active_join_coin_grants(
    db: AsyncSession, user_id: int, activity_id: int
) -> list[WanderCoinTransaction]:
    """查找尚未扣回的报名晃晃币发放流水（含历史 ref_type=activity）。"""
    result = await db.execute(
        select(WanderCoinTransaction).where(
            WanderCoinTransaction.user_id == user_id,
            WanderCoinTransaction.ref_id == activity_id,
            WanderCoinTransaction.amount > 0,
            WanderCoinTransaction.tx_type == JOIN_COIN_TX_TYPE,
            or_(
                WanderCoinTransaction.ref_type == JOIN_COIN_REF_TYPE,
                and_(
                    WanderCoinTransaction.ref_type == JOIN_COIN_REF_TYPE_LEGACY,
                    WanderCoinTransaction.remark == JOIN_COIN_REMARK,
                ),
            ),
        )
    )
    return list(result.scalars().all())


async def _find_active_join_point_grants(
    db: AsyncSession, user_id: int, activity_id: int
) -> list[PointRecord]:
    """查找尚未扣回的报名积分发放流水（不含打卡等同 reason 记录）。"""
    result = await db.execute(
        select(PointRecord).where(
            PointRecord.user_id == user_id,
            PointRecord.ref_id == activity_id,
            PointRecord.points > 0,
            PointRecord.reason == JOIN_POINT_REASON,
            PointRecord.reason_detail == JOIN_POINT_DETAIL,
            PointRecord.ref_type.in_(
                (JOIN_POINT_REF_TYPE, JOIN_POINT_REF_TYPE_LEGACY)
            ),
        )
    )
    return list(result.scalars().all())


async def revoke_enrollment_rewards(
    db: AsyncSession,
    user_id: int,
    activity: Activity,
) -> dict:
    """
    用户退出活动时扣除本轮报名奖励

    扣除规则：
    - 晃晃币：按未扣回的报名发放流水合计扣除
    - 积分：按未扣回的报名发放流水合计扣除
    - 删除对应发放流水，使再报名可再次获得奖励

    Returns:
        扣除统计信息 {"coins": int, "points": int}
    """
    stats = {"coins": 0, "points": 0}
    reason_prefix = f"退出活动扣除（{activity.title}）"

    coin_grants = await _find_active_join_coin_grants(db, user_id, activity.id)
    point_grants = await _find_active_join_point_grants(db, user_id, activity.id)

    if not coin_grants and not point_grants:
        logger.info(
            "用户 %s 退出活动 %s：无待扣除的报名奖励，跳过",
            user_id,
            activity.id,
        )
        return stats

    coins_to_revoke = sum(int(g.amount) for g in coin_grants)
    points_to_revoke = sum(int(p.points) for p in point_grants)

    if coins_to_revoke > 0:
        wallet = await get_or_create_wallet(db, user_id, for_update=True)
        wallet.balance -= coins_to_revoke
        wallet.total_spent += coins_to_revoke

        db.add(
            WanderCoinTransaction(
                user_id=user_id,
                amount=-coins_to_revoke,
                balance_after=wallet.balance,
                tx_type=CANCEL_COIN_TX_TYPE,
                ref_type=CANCEL_COIN_REF_TYPE,
                ref_id=activity.id,
                remark=reason_prefix,
            )
        )
        await db.flush()
        stats["coins"] = coins_to_revoke

        grant_ids = [g.id for g in coin_grants]
        await db.execute(
            delete(WanderCoinTransaction).where(
                WanderCoinTransaction.id.in_(grant_ids)
            )
        )

    if points_to_revoke > 0:
        user_level = await db.scalar(
            select(UserLevel)
            .where(UserLevel.user_id == user_id)
            .with_for_update()
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
        user_level.total_points -= points_to_revoke

        db.add(
            PointRecord(
                user_id=user_id,
                points=-points_to_revoke,
                points_before=points_before,
                points_after=user_level.total_points,
                reason=CANCEL_POINT_REASON,
                reason_detail=reason_prefix,
                ref_type=CANCEL_COIN_REF_TYPE,
                ref_id=activity.id,
            )
        )
        await db.flush()
        stats["points"] = points_to_revoke

        grant_ids = [p.id for p in point_grants]
        await db.execute(
            delete(PointRecord).where(PointRecord.id.in_(grant_ids))
        )

    logger.info(
        "用户 %s 退出活动 %s，扣除本轮报名奖励: 晃晃币-%s, 积分-%s",
        user_id,
        activity.id,
        stats["coins"],
        stats["points"],
    )
    return stats
