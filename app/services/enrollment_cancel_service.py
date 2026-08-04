"""
报名奖励发放 / 退出扣除

多轮「报名 → 取消 → 再报名」：
- 保留全部流水（不删发放记录），交易/积分列表成对可见
- 用「净未扣回余额」决定是否发放或扣除，防白嫖与连点重复扣
- 每轮发放使用独立 ref_id（activity_id * 1e6 + round），避开 grant 幂等键冲突
"""
from __future__ import annotations

import logging

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.trust_level import PointRecord
from app.models.wander_coin import WanderCoinTransaction
from app.services.user_level import add_points, get_or_create_user_level
from app.services.wander_coin_service import get_or_create_wallet, grant_coins

logger = logging.getLogger(__name__)

JOIN_REWARD_AMOUNT = 5
JOIN_REF_MULTIPLIER = 1_000_000

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


def encode_join_ref_id(activity_id: int, round_no: int) -> int:
    return activity_id * JOIN_REF_MULTIPLIER + round_no


def _join_coin_grant_clause(activity_id: int):
    lo = activity_id * JOIN_REF_MULTIPLIER
    hi = (activity_id + 1) * JOIN_REF_MULTIPLIER
    return and_(
        WanderCoinTransaction.tx_type == JOIN_COIN_TX_TYPE,
        WanderCoinTransaction.amount > 0,
        or_(
            and_(
                WanderCoinTransaction.ref_type == JOIN_COIN_REF_TYPE,
                or_(
                    WanderCoinTransaction.ref_id == activity_id,
                    and_(
                        WanderCoinTransaction.ref_id >= lo,
                        WanderCoinTransaction.ref_id < hi,
                    ),
                ),
            ),
            and_(
                WanderCoinTransaction.ref_type == JOIN_COIN_REF_TYPE_LEGACY,
                WanderCoinTransaction.ref_id == activity_id,
                WanderCoinTransaction.remark == JOIN_COIN_REMARK,
            ),
        ),
    )


def _join_coin_cancel_clause(activity_id: int):
    return and_(
        WanderCoinTransaction.tx_type == CANCEL_COIN_TX_TYPE,
        WanderCoinTransaction.ref_type == CANCEL_COIN_REF_TYPE,
        WanderCoinTransaction.ref_id == activity_id,
        WanderCoinTransaction.amount < 0,
    )


def _join_point_grant_clause(activity_id: int):
    lo = activity_id * JOIN_REF_MULTIPLIER
    hi = (activity_id + 1) * JOIN_REF_MULTIPLIER
    return and_(
        PointRecord.points > 0,
        PointRecord.reason == JOIN_POINT_REASON,
        PointRecord.reason_detail == JOIN_POINT_DETAIL,
        or_(
            and_(
                PointRecord.ref_type == JOIN_POINT_REF_TYPE,
                or_(
                    PointRecord.ref_id == activity_id,
                    and_(PointRecord.ref_id >= lo, PointRecord.ref_id < hi),
                ),
            ),
            and_(
                PointRecord.ref_type == JOIN_POINT_REF_TYPE_LEGACY,
                PointRecord.ref_id == activity_id,
            ),
        ),
    )


def _join_point_cancel_clause(activity_id: int):
    return and_(
        PointRecord.reason == CANCEL_POINT_REASON,
        PointRecord.ref_type == CANCEL_COIN_REF_TYPE,
        PointRecord.ref_id == activity_id,
        PointRecord.points < 0,
    )


async def _join_coin_net(db: AsyncSession, user_id: int, activity_id: int) -> int:
    grant_sum = await db.scalar(
        select(func.coalesce(func.sum(WanderCoinTransaction.amount), 0)).where(
            WanderCoinTransaction.user_id == user_id,
            _join_coin_grant_clause(activity_id),
        )
    )
    cancel_sum = await db.scalar(
        select(func.coalesce(func.sum(WanderCoinTransaction.amount), 0)).where(
            WanderCoinTransaction.user_id == user_id,
            _join_coin_cancel_clause(activity_id),
        )
    )
    return int(grant_sum or 0) + int(cancel_sum or 0)


async def _join_point_net(db: AsyncSession, user_id: int, activity_id: int) -> int:
    grant_sum = await db.scalar(
        select(func.coalesce(func.sum(PointRecord.points), 0)).where(
            PointRecord.user_id == user_id,
            _join_point_grant_clause(activity_id),
        )
    )
    cancel_sum = await db.scalar(
        select(func.coalesce(func.sum(PointRecord.points), 0)).where(
            PointRecord.user_id == user_id,
            _join_point_cancel_clause(activity_id),
        )
    )
    return int(grant_sum or 0) + int(cancel_sum or 0)


async def _next_join_coin_round(db: AsyncSession, user_id: int, activity_id: int) -> int:
    cnt = await db.scalar(
        select(func.count(WanderCoinTransaction.id)).where(
            WanderCoinTransaction.user_id == user_id,
            _join_coin_grant_clause(activity_id),
        )
    )
    return int(cnt or 0) + 1


async def _next_join_point_round(db: AsyncSession, user_id: int, activity_id: int) -> int:
    cnt = await db.scalar(
        select(func.count(PointRecord.id)).where(
            PointRecord.user_id == user_id,
            _join_point_grant_clause(activity_id),
        )
    )
    return int(cnt or 0) + 1


async def _latest_join_coin_tx(
    db: AsyncSession, user_id: int, activity_id: int
) -> WanderCoinTransaction | None:
    return await db.scalar(
        select(WanderCoinTransaction)
        .where(
            WanderCoinTransaction.user_id == user_id,
            _join_coin_grant_clause(activity_id),
        )
        .order_by(WanderCoinTransaction.id.desc())
        .limit(1)
    )


async def _latest_join_point_record(
    db: AsyncSession, user_id: int, activity_id: int
) -> PointRecord | None:
    return await db.scalar(
        select(PointRecord)
        .where(
            PointRecord.user_id == user_id,
            _join_point_grant_clause(activity_id),
        )
        .order_by(PointRecord.id.desc())
        .limit(1)
    )


async def grant_enrollment_rewards(
    db: AsyncSession,
    user_id: int,
    activity_id: int,
) -> dict:
    """
    报名发放本轮奖励。若净未扣回余额 > 0（仍占用上一轮奖励），则不再发放。
    """
    # 先锁钱包，再算净值，避免连点并发重复发放
    await get_or_create_wallet(db, user_id, for_update=True)
    coin_net = await _join_coin_net(db, user_id, activity_id)

    coin_tx_id: int | None = None
    if coin_net > 0:
        latest = await _latest_join_coin_tx(db, user_id, activity_id)
        coin_tx_id = latest.id if latest else None
        logger.info(
            "报名晃晃币跳过(仍有未扣回): user_id=%s activity_id=%s net=%s",
            user_id,
            activity_id,
            coin_net,
        )
    else:
        round_no = await _next_join_coin_round(db, user_id, activity_id)
        tx = await grant_coins(
            db,
            user_id,
            JOIN_REWARD_AMOUNT,
            tx_type=JOIN_COIN_TX_TYPE,
            ref_type=JOIN_COIN_REF_TYPE,
            ref_id=encode_join_ref_id(activity_id, round_no),
            remark=JOIN_COIN_REMARK,
        )
        coin_tx_id = tx.id

    await get_or_create_user_level(db, user_id, for_update=True)
    point_net = await _join_point_net(db, user_id, activity_id)

    point_record_id: int | None = None
    if point_net > 0:
        latest = await _latest_join_point_record(db, user_id, activity_id)
        point_record_id = latest.id if latest else None
        logger.info(
            "报名积分跳过(仍有未扣回): user_id=%s activity_id=%s net=%s",
            user_id,
            activity_id,
            point_net,
        )
    else:
        round_no = await _next_join_point_round(db, user_id, activity_id)
        record = await add_points(
            db,
            user_id,
            JOIN_REWARD_AMOUNT,
            reason=JOIN_POINT_REASON,
            reason_detail=JOIN_POINT_DETAIL,
            ref_type=JOIN_POINT_REF_TYPE,
            ref_id=encode_join_ref_id(activity_id, round_no),
        )
        point_record_id = record.id

    return {"coin_tx_id": coin_tx_id, "point_record_id": point_record_id}


async def revoke_enrollment_rewards(
    db: AsyncSession,
    user_id: int,
    activity: Activity,
) -> dict:
    """
    退出时按净未扣回余额扣除；不删除历史发放流水。
    """
    stats = {"coins": 0, "points": 0}
    reason_prefix = f"退出活动扣除（{activity.title}）"

    await get_or_create_wallet(db, user_id, for_update=True)
    coin_net = await _join_coin_net(db, user_id, activity.id)

    if coin_net > 0:
        wallet = await get_or_create_wallet(db, user_id, for_update=True)
        wallet.balance -= coin_net
        wallet.total_spent += coin_net
        db.add(
            WanderCoinTransaction(
                user_id=user_id,
                amount=-coin_net,
                balance_after=wallet.balance,
                tx_type=CANCEL_COIN_TX_TYPE,
                ref_type=CANCEL_COIN_REF_TYPE,
                ref_id=activity.id,
                remark=reason_prefix,
            )
        )
        await db.flush()
        stats["coins"] = coin_net
    else:
        logger.info(
            "用户 %s 退出活动 %s：晃晃币无待扣余额(net=%s)",
            user_id,
            activity.id,
            coin_net,
        )

    await get_or_create_user_level(db, user_id, for_update=True)
    point_net = await _join_point_net(db, user_id, activity.id)

    if point_net > 0:
        user_level = await get_or_create_user_level(db, user_id, for_update=True)
        points_before = user_level.total_points
        user_level.total_points -= point_net
        db.add(
            PointRecord(
                user_id=user_id,
                points=-point_net,
                points_before=points_before,
                points_after=user_level.total_points,
                reason=CANCEL_POINT_REASON,
                reason_detail=reason_prefix,
                ref_type=CANCEL_COIN_REF_TYPE,
                ref_id=activity.id,
            )
        )
        await db.flush()
        stats["points"] = point_net
    else:
        logger.info(
            "用户 %s 退出活动 %s：积分无待扣余额(net=%s)",
            user_id,
            activity.id,
            point_net,
        )

    if stats["coins"] or stats["points"]:
        logger.info(
            "用户 %s 退出活动 %s，扣除本轮报名奖励: 晃晃币-%s, 积分-%s",
            user_id,
            activity.id,
            stats["coins"],
            stats["points"],
        )
    return stats
