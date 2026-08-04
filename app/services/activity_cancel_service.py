"""活动取消时的奖励扣除服务

复用 enrollment_cancel_service 的 outstanding 栈配对机制，
确保多轮「报名→退出→报名→活动取消」场景下不会重复扣除。

扣除规则（与报名奖励对称）：
- 创建人：发布活动奖励（晃晃币-10, 积分-10）
- 参与人：报名活动奖励（晃晃币-5, 积分-5）— 使用 outstanding 机制
- 已打卡参与人：额外扣除打卡奖励（晃晃币-15, 信誉分-10, 积分-15）
"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.level_config import get_level_by_points
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.growth_trust import ActivityCheckin, UserTrustProfile
from app.models.trust_level import PointRecord, TrustScoreRecord, UserLevel
from app.models.wander_coin import WanderCoinTransaction, WanderCoinWallet
from app.services.enrollment_cancel_service import (
    ACTIVITY_CANCEL_COIN_TX_TYPE,
    ACTIVITY_CANCEL_POINT_REASON,
    ACTIVITY_CANCEL_REF_TYPE,
    _join_coin_outstanding,
    _join_point_outstanding,
)
from app.services.trust_score import record_trust_score_change
from app.services.wander_coin_service import get_or_create_wallet

logger = logging.getLogger(__name__)

# 打卡奖励的扣除（幂等 ref_type）
CHECKIN_CANCEL_TX_TYPE = "activity_cancel_deduct"
CHECKIN_CANCEL_REF_TYPE = "activity_checkin_cancel"
CHECKIN_CANCEL_POINT_REASON = "checkin_cancel_deduct"

PUBLISH_COIN_TX_TYPE = "activity_cancel_deduct"
PUBLISH_REF_TYPE = "activity_publish_cancel"
PUBLISH_POINT_REASON = "publish_cancel_deduct"


async def _revoke_coins(
    db: AsyncSession,
    user_id: int,
    amount: int,
    tx_type: str,
    ref_type: str,
    ref_id: int,
    remark: str,
    *,
    check_deduct_type: str | None = None,
    check_ref_type: str | None = None,
    check_ref_id: int | None = None,
) -> int:
    """扣除晃晃币（cap 到 balance，防负数）。返回实际扣除额。"""
    wallet = await get_or_create_wallet(db, user_id, for_update=True)
    actual = min(amount, max(0, wallet.balance))
    if actual <= 0:
        return 0

    wallet.balance -= actual

    tx = WanderCoinTransaction(
        user_id=user_id,
        amount=-actual,
        balance_after=wallet.balance,
        tx_type=tx_type,
        ref_type=ref_type,
        ref_id=ref_id,
        remark=remark,
    )
    db.add(tx)
    await db.flush()
    return actual


async def _revoke_points(
    db: AsyncSession,
    user_id: int,
    amount: int,
    reason: str,
    reason_detail: str,
    ref_type: str,
    ref_id: int,
) -> int:
    """扣除积分（cap 到 total_points，含等级重算）。返回实际扣除额。"""
    user_level_result = await db.execute(
        select(UserLevel).where(UserLevel.user_id == user_id).with_for_update()
    )
    user_level = user_level_result.scalar_one_or_none()
    if not user_level:
        return 0

    actual = min(amount, max(0, user_level.total_points))
    if actual <= 0:
        return 0

    points_before = user_level.total_points
    points_after = points_before - actual
    user_level.total_points = points_after
    level_code, level_name = get_level_by_points(points_after)
    user_level.level_code = level_code
    user_level.level_name = level_name
    user_level.updated_at = datetime.now()

    db.add(
        PointRecord(
            user_id=user_id,
            points=-actual,
            points_before=points_before,
            points_after=points_after,
            reason=reason,
            reason_detail=reason_detail,
            ref_type=ref_type,
            ref_id=ref_id,
        )
    )
    await db.flush()
    return actual


async def _check_coin_idempotent(
    db: AsyncSession, user_id: int, tx_type: str, ref_type: str, ref_id: int
) -> bool:
    """检查是否已存在扣除记录，返回 True 表示已扣过。"""
    row = await db.scalar(
        select(WanderCoinTransaction).where(
            WanderCoinTransaction.user_id == user_id,
            WanderCoinTransaction.tx_type == tx_type,
            WanderCoinTransaction.ref_type == ref_type,
            WanderCoinTransaction.ref_id == ref_id,
        )
    )
    return row is not None


async def _check_point_idempotent(
    db: AsyncSession, user_id: int, reason: str, ref_type: str, ref_id: int
) -> bool:
    """检查积分扣除是否已存在，返回 True 表示已扣过。"""
    row = await db.scalar(
        select(PointRecord).where(
            PointRecord.user_id == user_id,
            PointRecord.reason == reason,
            PointRecord.ref_type == ref_type,
            PointRecord.ref_id == ref_id,
        )
    )
    return row is not None


async def revoke_activity_rewards(
    db: AsyncSession,
    activity: Activity,
    cancel_reason: str | None = None,
) -> dict:
    """活动取消时扣除相关奖励。

    扣除规则：
    - 创建人：扣除发布活动奖励（晃晃币-10, 积分-10）
    - 参与人：扣除报名活动奖励 — 使用 outstanding 机制（晃晃币-5, 积分-5）
    - 已打卡参与人：额外扣除打卡奖励（晃晃币-15, 信誉分-10, 积分-15）

    所有扣除记录都会写入流水，用户可在列表中查看。
    使用幂等检查防止重复扣除。
    """
    stats = {
        "organizer": {"coins": 0, "points": 0},
        "participants": {"count": 0, "coins": 0, "points": 0},
        "checkins": {"count": 0, "coins": 0, "trust_score": 0, "points": 0},
    }

    reason_prefix = "活动取消扣除"
    if cancel_reason:
        reason_prefix += f"（{cancel_reason}）"

    # ── 1. 扣除创建人的发布活动奖励（幂等） ──
    try:
        if not await _check_coin_idempotent(
            db, activity.organizer_id,
            PUBLISH_COIN_TX_TYPE, PUBLISH_REF_TYPE, activity.id,
        ):
            stats["organizer"]["coins"] = await _revoke_coins(
                db, activity.organizer_id, 10,
                tx_type=PUBLISH_COIN_TX_TYPE,
                ref_type=PUBLISH_REF_TYPE,
                ref_id=activity.id,
                remark=f"{reason_prefix} - 发布活动奖励",
            )

        if not await _check_point_idempotent(
            db, activity.organizer_id,
            PUBLISH_POINT_REASON, PUBLISH_REF_TYPE, activity.id,
        ):
            stats["organizer"]["points"] = await _revoke_points(
                db, activity.organizer_id, 10,
                reason=PUBLISH_POINT_REASON,
                reason_detail=f"{reason_prefix} - 发布活动奖励",
                ref_type=PUBLISH_REF_TYPE,
                ref_id=activity.id,
            )
    except Exception:
        logger.exception(
            "扣除创建人 %s 奖励失败", activity.organizer_id
        )

    # ── 2. 扣除参与人的报名活动奖励（使用 outstanding 机制） ──
    enrollments_result = await db.execute(
        select(ActivityEnrollment).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.status == "joined",
        )
    )
    enrollments = enrollments_result.scalars().all()

    for enrollment in enrollments:
        if enrollment.user_id == activity.organizer_id:
            continue  # 创建人已在上面处理

        try:
            # 使用 enrollment_cancel_service 的 outstanding 机制
            coin_outstanding = await _join_coin_outstanding(
                db, enrollment.user_id, activity.id
            )
            point_outstanding = await _join_point_outstanding(
                db, enrollment.user_id, activity.id
            )

            deducted_coins = 0
            deducted_points = 0

            if coin_outstanding > 0:
                deducted_coins = await _revoke_coins(
                    db, enrollment.user_id, coin_outstanding,
                    tx_type=ACTIVITY_CANCEL_COIN_TX_TYPE,
                    ref_type=ACTIVITY_CANCEL_REF_TYPE,
                    ref_id=activity.id,
                    remark=f"{reason_prefix} - 报名活动奖励",
                )

            if point_outstanding > 0:
                deducted_points = await _revoke_points(
                    db, enrollment.user_id, point_outstanding,
                    reason=ACTIVITY_CANCEL_POINT_REASON,
                    reason_detail=f"{reason_prefix} - 报名活动奖励",
                    ref_type=ACTIVITY_CANCEL_REF_TYPE,
                    ref_id=activity.id,
                )

            if deducted_coins or deducted_points:
                stats["participants"]["coins"] += deducted_coins
                stats["participants"]["points"] += deducted_points
                stats["participants"]["count"] += 1

        except Exception:
            logger.exception(
                "扣除参与人 %s 奖励失败", enrollment.user_id
            )

    # ── 3. 扣除已打卡参与人的打卡奖励（幂等） ──
    checkins_result = await db.execute(
        select(ActivityCheckin).where(
            ActivityCheckin.activity_id == activity.id,
        )
    )
    checkins = checkins_result.scalars().all()

    for checkin in checkins:
        try:
            # 晃晃币 -15（幂等）
            deducted_coins = 0
            if not await _check_coin_idempotent(
                db, checkin.user_id,
                CHECKIN_CANCEL_TX_TYPE, CHECKIN_CANCEL_REF_TYPE, activity.id,
            ):
                deducted_coins = await _revoke_coins(
                    db, checkin.user_id, 15,
                    tx_type=CHECKIN_CANCEL_TX_TYPE,
                    ref_type=CHECKIN_CANCEL_REF_TYPE,
                    ref_id=activity.id,
                    remark=f"{reason_prefix} - 打卡活动奖励",
                )

            # 信誉分 -10（幂等）
            deducted_trust = 0
            trust_result = await db.execute(
                select(UserTrustProfile).where(
                    UserTrustProfile.user_id == checkin.user_id
                ).with_for_update()
            )
            user_trust = trust_result.scalar_one_or_none()
            if user_trust:
                trust_before = user_trust.trust_score
                trust_deduct = min(10, trust_before)
                if trust_deduct > 0:
                    # 幂等：同一 ref 只扣一次
                    existing_trust = await db.scalar(
                        select(TrustScoreRecord).where(
                            TrustScoreRecord.user_id == checkin.user_id,
                            TrustScoreRecord.reason == "activity_cancel_deduct",
                            TrustScoreRecord.ref_type == CHECKIN_CANCEL_REF_TYPE,
                            TrustScoreRecord.ref_id == activity.id,
                        )
                    )
                    if not existing_trust:
                        user_trust.trust_score -= trust_deduct
                        db.add(
                            TrustScoreRecord(
                                user_id=checkin.user_id,
                                change=-trust_deduct,
                                trust_score_before=trust_before,
                                trust_score_after=user_trust.trust_score,
                                reason="activity_cancel_deduct",
                                reason_detail=f"{reason_prefix} - 打卡活动奖励",
                                ref_type=CHECKIN_CANCEL_REF_TYPE,
                                ref_id=activity.id,
                            )
                        )
                        deducted_trust = trust_deduct

            # 积分 -15（幂等）
            deducted_points = 0
            if not await _check_point_idempotent(
                db, checkin.user_id,
                CHECKIN_CANCEL_POINT_REASON, CHECKIN_CANCEL_REF_TYPE, activity.id,
            ):
                deducted_points = await _revoke_points(
                    db, checkin.user_id, 15,
                    reason=CHECKIN_CANCEL_POINT_REASON,
                    reason_detail=f"{reason_prefix} - 打卡活动奖励",
                    ref_type=CHECKIN_CANCEL_REF_TYPE,
                    ref_id=activity.id,
                )

            if deducted_coins or deducted_trust or deducted_points:
                stats["checkins"]["coins"] += deducted_coins
                stats["checkins"]["trust_score"] += deducted_trust
                stats["checkins"]["points"] += deducted_points
                stats["checkins"]["count"] += 1

        except Exception:
            logger.exception(
                "扣除打卡人 %s 奖励失败", checkin.user_id
            )

    return stats
