"""
报名奖励发放 / 退出扣除

多轮「报名 → 取消 → 再报名」：
- 保留全部流水（不删发放记录），交易/积分列表成对可见
- 按时间序栈配对计算「未扣回轮次」：历史多扣的取消不阻断本轮扣除
- 每轮发放使用独立 ref_id（activity_id * 1e6 + round），避开 grant 幂等键冲突
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.trust_level import PointRecord
from app.models.wander_coin import WanderCoinTransaction
from app.core.level_config import get_level_by_points
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

# 活动取消（区别于用户主动退出）
ACTIVITY_CANCEL_COIN_TX_TYPE = "activity_cancel_deduct"
ACTIVITY_CANCEL_REF_TYPE = "activity_cancel"
ACTIVITY_CANCEL_POINT_REASON = "activity_cancel_deduct"


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
    """匹配所有退出/取消类扣除记录（含 enrollment_cancel + activity_cancel + 旧数据）"""
    return and_(
        WanderCoinTransaction.tx_type.in_([
            CANCEL_COIN_TX_TYPE,              # "enrollment_cancel_deduct"
            ACTIVITY_CANCEL_COIN_TX_TYPE,     # "activity_cancel_deduct"
        ]),
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
    """匹配所有退出/取消类积分扣除记录"""
    return and_(
        PointRecord.reason.in_([CANCEL_POINT_REASON, ACTIVITY_CANCEL_POINT_REASON]),
        PointRecord.ref_id == activity_id,
        PointRecord.points < 0,
    )


@dataclass(frozen=True)
class _LedgerEvent:
    id: int
    kind: str  # "grant" | "cancel"
    amount: int  # grant 为正；cancel 存绝对值


def _outstanding_from_events(events: list[_LedgerEvent]) -> int:
    """按 id 序栈配对：grant 入栈，cancel 出栈；多余历史 cancel 忽略。"""
    stack: list[int] = []
    for ev in events:
        if ev.kind == "grant":
            stack.append(ev.amount)
        elif stack:
            stack.pop()
    return sum(stack)


async def _join_coin_outstanding(
    db: AsyncSession, user_id: int, activity_id: int
) -> int:
    grant_rows = (
        await db.execute(
            select(
                WanderCoinTransaction.id, WanderCoinTransaction.amount
            ).where(
                WanderCoinTransaction.user_id == user_id,
                _join_coin_grant_clause(activity_id),
            )
        )
    ).all()
    cancel_rows = (
        await db.execute(
            select(
                WanderCoinTransaction.id, WanderCoinTransaction.amount
            ).where(
                WanderCoinTransaction.user_id == user_id,
                _join_coin_cancel_clause(activity_id),
            )
        )
    ).all()
    events = [
        *[_LedgerEvent(int(r.id), "grant", int(r.amount)) for r in grant_rows],
        *[
            _LedgerEvent(int(r.id), "cancel", abs(int(r.amount)))
            for r in cancel_rows
        ],
    ]
    events.sort(key=lambda e: e.id)
    return _outstanding_from_events(events)


async def _join_point_outstanding(
    db: AsyncSession, user_id: int, activity_id: int
) -> int:
    grant_rows = (
        await db.execute(
            select(PointRecord.id, PointRecord.points).where(
                PointRecord.user_id == user_id,
                _join_point_grant_clause(activity_id),
            )
        )
    ).all()
    cancel_rows = (
        await db.execute(
            select(PointRecord.id, PointRecord.points).where(
                PointRecord.user_id == user_id,
                _join_point_cancel_clause(activity_id),
            )
        )
    ).all()
    events = [
        *[_LedgerEvent(int(r.id), "grant", int(r.points)) for r in grant_rows],
        *[
            _LedgerEvent(int(r.id), "cancel", abs(int(r.points)))
            for r in cancel_rows
        ],
    ]
    events.sort(key=lambda e: e.id)
    return _outstanding_from_events(events)


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
    """报名发放本轮奖励。若仍有未配对的发放，则不再发放。"""
    await get_or_create_wallet(db, user_id, for_update=True)
    coin_outstanding = await _join_coin_outstanding(db, user_id, activity_id)

    coin_tx_id: int | None = None
    if coin_outstanding > 0:
        latest = await _latest_join_coin_tx(db, user_id, activity_id)
        coin_tx_id = latest.id if latest else None
        logger.info(
            "报名晃晃币跳过(仍有未扣回): user_id=%s activity_id=%s outstanding=%s",
            user_id,
            activity_id,
            coin_outstanding,
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
    point_outstanding = await _join_point_outstanding(db, user_id, activity_id)

    point_record_id: int | None = None
    if point_outstanding > 0:
        latest = await _latest_join_point_record(db, user_id, activity_id)
        point_record_id = latest.id if latest else None
        logger.info(
            "报名积分跳过(仍有未扣回): user_id=%s activity_id=%s outstanding=%s",
            user_id,
            activity_id,
            point_outstanding,
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
    """退出时扣除未配对的报名奖励；不删除历史发放流水。"""
    stats = {"coins": 0, "points": 0}
    reason_prefix = f"退出活动扣除（{activity.title}）"

    await get_or_create_wallet(db, user_id, for_update=True)
    coin_outstanding = await _join_coin_outstanding(db, user_id, activity.id)

    if coin_outstanding > 0:
        wallet = await get_or_create_wallet(db, user_id, for_update=True)
        actual_deduct = min(coin_outstanding, max(0, wallet.balance))
        wallet.balance -= actual_deduct
        db.add(
            WanderCoinTransaction(
                user_id=user_id,
                amount=-actual_deduct,
                balance_after=wallet.balance,
                tx_type=CANCEL_COIN_TX_TYPE,
                ref_type=CANCEL_COIN_REF_TYPE,
                ref_id=activity.id,
                remark=reason_prefix,
            )
        )
        await db.flush()
        stats["coins"] = actual_deduct
    else:
        logger.info(
            "用户 %s 退出活动 %s：晃晃币无待扣(outstanding=%s)",
            user_id,
            activity.id,
            coin_outstanding,
        )

    await get_or_create_user_level(db, user_id, for_update=True)
    point_outstanding = await _join_point_outstanding(db, user_id, activity.id)

    if point_outstanding > 0:
        user_level = await get_or_create_user_level(db, user_id, for_update=True)
        actual_point_deduct = min(point_outstanding, max(0, user_level.total_points))

        points_before = user_level.total_points
        points_after = points_before - actual_point_deduct
        user_level.total_points = points_after
        level_code, level_name = get_level_by_points(points_after)
        user_level.level_code = level_code
        user_level.level_name = level_name
        user_level.updated_at = datetime.now()

        db.add(
            PointRecord(
                user_id=user_id,
                points=-actual_point_deduct,
                points_before=points_before,
                points_after=points_after,
                reason=CANCEL_POINT_REASON,
                reason_detail=reason_prefix,
                ref_type=CANCEL_COIN_REF_TYPE,
                ref_id=activity.id,
            )
        )
        await db.flush()
        stats["points"] = actual_point_deduct
    else:
        logger.info(
            "用户 %s 退出活动 %s：积分无待扣(outstanding=%s)",
            user_id,
            activity.id,
            point_outstanding,
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
