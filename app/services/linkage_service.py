"""三体系联动服务层

协调晃晃币、信誉分、积分三个体系的联动奖励/惩罚逻辑。
每个体系独立 try/except，单个体系失败不阻断其他体系。
"""
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import wander_coin_service
from app.services.trust_score import record_trust_score_change
from app.services.user_level import add_points

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 辅助函数（错误隔离）
# ---------------------------------------------------------------------------

async def _safe_grant_coins(
    db: AsyncSession,
    user_id: int,
    amount: int,
    tx_type: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
    remark: str | None = None,
) -> int | None:
    """安全发放晃晃币，失败时记录日志并返回 None。"""
    try:
        tx = await wander_coin_service.grant_coins(
            db, user_id, amount,
            tx_type=tx_type,
            ref_type=ref_type,
            ref_id=ref_id,
            remark=remark,
        )
        return tx.id if tx else None
    except Exception:
        logger.exception("晃晃币发放失败: user=%s amount=%s type=%s", user_id, amount, tx_type)
        return None


async def _safe_change_trust(
    db: AsyncSession,
    user_id: int,
    change: int,
    reason: str,
    reason_detail: str = "",
    ref_type: str | None = None,
    ref_id: int | None = None,
) -> int | None:
    """安全变更信誉分，失败时记录日志并返回 None。"""
    try:
        record = await record_trust_score_change(
            db, user_id, change,
            reason=reason,
            reason_detail=reason_detail,
            ref_type=ref_type,
            ref_id=ref_id,
        )
        return record.id
    except Exception:
        logger.exception("信誉分变更失败: user=%s change=%s reason=%s", user_id, change, reason)
        return None


async def _safe_add_points(
    db: AsyncSession,
    user_id: int,
    points: int,
    reason: str,
    reason_detail: str = "",
    ref_type: str | None = None,
    ref_id: int | None = None,
) -> int | None:
    """安全变更积分，失败时记录日志并返回 None。"""
    try:
        record = await add_points(
            db, user_id, points,
            reason=reason,
            reason_detail=reason_detail,
            ref_type=ref_type,
            ref_id=ref_id,
        )
        return record.id
    except Exception:
        logger.exception("积分变更失败: user=%s points=%s reason=%s", user_id, points, reason)
        return None


# ---------------------------------------------------------------------------
# 消费
# ---------------------------------------------------------------------------

async def spend_wander_coins(
    db: AsyncSession,
    user_id: int,
    amount: int,
    reason: str,
    detail: str | None = None,
    ref_type: str | None = None,
    ref_id: int | str | None = None,
) -> bool:
    """消费晃晃币（联动层封装）"""
    if isinstance(ref_id, str):
        try:
            ref_id = int(ref_id)
        except (ValueError, TypeError):
            ref_id = None

    tx = await wander_coin_service.spend_coins(
        db=db, user_id=user_id, amount=amount,
        tx_type="spend", ref_type=ref_type, ref_id=ref_id,
        remark=detail or reason,
    )
    return tx is not None


# ---------------------------------------------------------------------------
# 正向行为（加分）
# ---------------------------------------------------------------------------

async def on_activity_publish(
    db: AsyncSession, user_id: int, activity_id: int,
) -> dict[str, Any]:
    """发布活动 → 晃晃币+10, 积分+10"""
    return {
        "coin_tx_id": await _safe_grant_coins(
            db, user_id, 10, "activity_reward", "activity", activity_id, "发布活动奖励",
        ),
        "point_record_id": await _safe_add_points(
            db, user_id, 10, "publish_activity", "发布活动", "activity", activity_id,
        ),
    }


async def on_activity_join(
    db: AsyncSession, user_id: int, activity_id: int,
) -> dict[str, Any]:
    """报名活动 → 晃晃币+5, 积分+5"""
    return {
        "coin_tx_id": await _safe_grant_coins(
            db, user_id, 5, "activity_reward", "activity", activity_id, "报名活动奖励",
        ),
        "point_record_id": await _safe_add_points(
            db, user_id, 5, "join_activity", "报名活动", "activity", activity_id,
        ),
    }


async def on_activity_checkin(
    db: AsyncSession, user_id: int, activity_id: int,
) -> dict[str, Any]:
    """活动打卡（三体系联动）→ 晃晃币+15, 信誉分+10, 积分+15"""
    result: dict[str, Any] = {
        "coin_tx_id": await _safe_grant_coins(
            db, user_id, 15, "activity_reward", "activity", activity_id, "活动打卡奖励",
        ),
        "trust_record_id": await _safe_change_trust(
            db, user_id, 10, "activity_checkin", "活动打卡", "activity", activity_id,
        ),
        "point_record_id": await _safe_add_points(
            db, user_id, 15, "join_activity", "活动打卡", "activity", activity_id,
        ),
    }
    # 检查连续活动奖励
    streak_result = await _check_activity_streak_reward(db, user_id)
    if streak_result:
        result["streak_reward"] = streak_result
    return result


async def on_activity_good_review(
    db: AsyncSession, user_id: int, activity_id: int,
) -> dict[str, Any]:
    """活动获好评 → 晃晃币+10, 信誉分+20, 积分+5"""
    return {
        "coin_tx_id": await _safe_grant_coins(
            db, user_id, 10, "activity_reward", "activity", activity_id, "活动获好评奖励",
        ),
        "trust_record_id": await _safe_change_trust(
            db, user_id, 20, "activity_good_review", "活动获好评", "activity", activity_id,
        ),
        "point_record_id": await _safe_add_points(
            db, user_id, 5, "receive_good_review", "活动获好评", "activity", activity_id,
        ),
    }


async def on_referral_register(
    db: AsyncSession, inviter_id: int, invitee_id: int | None = None,
) -> dict[str, Any]:
    """邀请好友注册 → 晃晃币+5, 积分+30"""
    result: dict[str, Any] = {
        "coin_tx_id": await _safe_grant_coins(
            db, inviter_id, 5, "referral_reward", "referral", invitee_id, "邀请好友注册",
        ),
        "point_record_id": await _safe_add_points(
            db, inviter_id, 30, "referral_register", "邀请好友注册", "referral", invitee_id,
        ),
    }
    # 检查邀请阶梯奖励
    milestone = await _check_referral_milestone(db, inviter_id)
    if milestone:
        result["milestone_reward"] = milestone
    return result


async def on_referral_first_join(
    db: AsyncSession, inviter_id: int, invitee_id: int, activity_id: int,
) -> dict[str, Any]:
    """好友首次参加活动（三体系联动）→ 晃晃币+20, 信誉分+15, 积分+20"""
    return {
        "coin_tx_id": await _safe_grant_coins(
            db, inviter_id, 20, "referral_reward", "referral", invitee_id, "好友首次参加活动",
        ),
        "trust_record_id": await _safe_change_trust(
            db, inviter_id, 15, "referral_first_join", "好友首次参加活动", "referral", invitee_id,
        ),
        "point_record_id": await _safe_add_points(
            db, inviter_id, 20, "referral_first_join", "好友首次参加活动", "referral", invitee_id,
        ),
    }


async def on_valid_report(
    db: AsyncSession, user_id: int, report_id: int,
) -> dict[str, Any]:
    """有效举报 → 信誉分+30, 积分+10"""
    return {
        "trust_record_id": await _safe_change_trust(
            db, user_id, 30, "report_confirmed", "有效举报", "report", report_id,
        ),
        "point_record_id": await _safe_add_points(
            db, user_id, 10, "valid_report", "有效举报", "report", report_id,
        ),
    }


async def on_post_comment(
    db: AsyncSession, user_id: int, post_id: int, comment_id: int,
) -> dict[str, Any]:
    """发布评论（仅积分）→ 积分+3"""
    return {
        "point_record_id": await _safe_add_points(
            db, user_id, 3, "post_comment", "发布评论", "post_comment", comment_id,
        ),
    }


# ---------------------------------------------------------------------------
# 负向行为（扣分）
# ---------------------------------------------------------------------------

# -- 信誉分扣分（履约问题）--

async def on_no_show(
    db: AsyncSession, user_id: int, activity_id: int,
) -> dict[str, Any]:
    """爽约（仅信誉分）→ 信誉分-50"""
    return {
        "trust_record_id": await _safe_change_trust(
            db, user_id, -50, "no_show", "活动爽约", "activity", activity_id,
        ),
    }


async def on_late_arrival(
    db: AsyncSession, user_id: int, activity_id: int,
) -> dict[str, Any]:
    """迟到 30 分钟+（仅信誉分）→ 信誉分-20"""
    return {
        "trust_record_id": await _safe_change_trust(
            db, user_id, -20, "late_arrival", "活动迟到超30分钟", "activity", activity_id,
        ),
    }


async def on_leader_mark_violation(
    db: AsyncSession, user_id: int, activity_id: int, leader_id: int,
) -> dict[str, Any]:
    """被团长标记违约（仅信誉分）→ 信誉分-80"""
    return {
        "trust_record_id": await _safe_change_trust(
            db, user_id, -80, "leader_mark_violation",
            f"被团长(id={leader_id})标记违约",
            "activity", activity_id,
        ),
    }


async def on_mass_complaint(
    db: AsyncSession, user_id: int, activity_id: int, complaint_count: int,
) -> dict[str, Any]:
    """被多人投诉（≥3人）（仅信誉分）→ 信誉分-100"""
    return {
        "trust_record_id": await _safe_change_trust(
            db, user_id, -100, "mass_complaint",
            f"同一活动被{complaint_count}人投诉",
            "activity", activity_id,
        ),
    }


async def on_activity_cancel_host(
    db: AsyncSession, user_id: int, activity_id: int,
) -> dict[str, Any]:
    """活动取消（发起人原因）（仅信誉分）→ 信誉分-30"""
    return {
        "trust_record_id": await _safe_change_trust(
            db, user_id, -30, "activity_cancel_host",
            "活动发起人在开始前24h内取消",
            "activity", activity_id,
        ),
    }


async def on_photo_fraud(
    db: AsyncSession, user_id: int, verification_id: int,
) -> dict[str, Any]:
    """照片验证造假（仅信誉分）→ 信誉分-200"""
    return {
        "trust_record_id": await _safe_change_trust(
            db, user_id, -200, "photo_fraud",
            "照片验证使用假照片",
            "photo_verification", verification_id,
        ),
    }


async def on_meet_review_bad(
    db: AsyncSession, user_id: int, review_id: int, activity_id: int,
) -> dict[str, Any]:
    """见面互评差评（仅信誉分）→ 信誉分-10"""
    return {
        "trust_record_id": await _safe_change_trust(
            db, user_id, -10, "meet_review_bad",
            "见面互评差评",
            "meet_review", review_id,
        ),
    }


# -- 积分扣分（社交/内容问题）--

async def on_bad_speech(
    db: AsyncSession, user_id: int, content_type: str, content_id: int,
) -> dict[str, Any]:
    """不当言论（仅积分）→ 积分-50"""
    result: dict[str, Any] = {
        "point_record_id": await _safe_add_points(
            db, user_id, -50, "bad_speech", "不当言论", content_type, content_id,
        ),
    }
    repeat = await _check_repeat_violation(db, user_id)
    if repeat:
        result["repeat_violation"] = repeat
    return result


async def on_violation_content(
    db: AsyncSession, user_id: int, content_type: str, content_id: int,
) -> dict[str, Any]:
    """违规内容（仅积分）→ 积分-80"""
    result: dict[str, Any] = {
        "point_record_id": await _safe_add_points(
            db, user_id, -80, "violation_content", "发布违规内容", content_type, content_id,
        ),
    }
    repeat = await _check_repeat_violation(db, user_id)
    if repeat:
        result["repeat_violation"] = repeat
    return result


async def on_complaint_confirmed(
    db: AsyncSession, user_id: int, complaint_id: int,
) -> dict[str, Any]:
    """被投诉经核实（仅积分）→ 积分-30"""
    result: dict[str, Any] = {
        "point_record_id": await _safe_add_points(
            db, user_id, -30, "complaint_confirmed", "被投诉经核实", "complaint", complaint_id,
        ),
    }
    repeat = await _check_repeat_violation(db, user_id)
    if repeat:
        result["repeat_violation"] = repeat
    return result


async def on_spam_behavior(
    db: AsyncSession, user_id: int, ref_type: str, ref_id: int,
) -> dict[str, Any]:
    """恶意刷评/刷量（仅积分）→ 积分-100"""
    return {
        "point_record_id": await _safe_add_points(
            db, user_id, -100, "spam_behavior", "恶意刷评/刷量", ref_type, ref_id,
        ),
    }


async def on_harassment(
    db: AsyncSession, user_id: int, complaint_id: int,
) -> dict[str, Any]:
    """骚扰其他用户（仅积分）→ 积分-80"""
    result: dict[str, Any] = {
        "point_record_id": await _safe_add_points(
            db, user_id, -80, "harassment", "骚扰其他用户", "complaint", complaint_id,
        ),
    }
    repeat = await _check_repeat_violation(db, user_id)
    if repeat:
        result["repeat_violation"] = repeat
    return result


async def on_severe_violation(
    db: AsyncSession, user_id: int, ref_type: str, ref_id: int,
) -> dict[str, Any]:
    """严重违规（涉黄/涉政/欺诈等）→ 积分-300，可同时冻结账号"""
    return {
        "point_record_id": await _safe_add_points(
            db, user_id, -300, "severe_violation", "严重违规", ref_type, ref_id,
        ),
    }


# ---------------------------------------------------------------------------
# 联动奖励检查
# ---------------------------------------------------------------------------

async def _check_activity_streak_reward(
    db: AsyncSession, user_id: int,
) -> dict[str, Any] | None:
    """检查连续活动奖励：30天内完成3次+30晃晃币，7次+80晃晃币。

    基于 activity_checkins 表的打卡记录统计。
    幂等：同一月份同一档位只奖励一次（通过 ref_type + ref_id 去重）。
    """
    from app.models.growth_trust import ActivityCheckin

    now = datetime.now()
    thirty_days_ago = now - timedelta(days=30)

    # 统计30天内打卡次数
    result = await db.execute(
        select(func.count(ActivityCheckin.id)).where(
            and_(
                ActivityCheckin.user_id == user_id,
                ActivityCheckin.checked_in_at >= thirty_days_ago,
            )
        )
    )
    checkin_count = result.scalar() or 0

    # 连续7次活动 +80（优先检查更高档）
    if checkin_count >= 7:
        ref_id = _streak_ref_id(user_id, "7")
        tx_id = await _safe_grant_coins(
            db, user_id, 80, "activity_reward",
            "streak_reward", ref_id,
            "30天内连续参加7次活动奖励",
        )
        if tx_id:
            return {"type": "streak_7", "coin_tx_id": tx_id, "amount": 80}

    # 连续3次活动 +30
    elif checkin_count >= 3:
        ref_id = _streak_ref_id(user_id, "3")
        tx_id = await _safe_grant_coins(
            db, user_id, 30, "activity_reward",
            "streak_reward", ref_id,
            "30天内连续参加3次活动奖励",
        )
        if tx_id:
            return {"type": "streak_3", "coin_tx_id": tx_id, "amount": 30}

    return None


def _streak_ref_id(user_id: int, tier: str) -> int:
    """生成连续活动奖励的幂等 ref_id（避免重复发放）。"""
    now = datetime.now()
    period = now.year * 100 + now.month
    return period * 10000 + user_id % 10000 + (70 if tier == "7" else 30)


async def _check_referral_milestone(
    db: AsyncSession, inviter_id: int,
) -> dict[str, Any] | None:
    """检查邀请阶梯奖励。

    里程碑: 3人(+100), 10人(+500), 30人(+2000), 100人(+5000)
    幂等：每个里程碑只奖励一次（ref_type=referral_milestone, ref_id=milestone_num）。
    """
    from app.models.growth_trust import ReferralBinding

    result = await db.execute(
        select(func.count(ReferralBinding.id)).where(
            ReferralBinding.inviter_id == inviter_id,
        )
    )
    total_invites = result.scalar() or 0

    # 里程碑定义：(人数门槛, 晃晃币奖励, 徽章名称)
    milestones = [
        (100, 5000, "旅游达人"),
        (30, 2000, None),
        (10, 500, "社交达人"),
        (3, 100, None),
    ]

    for threshold, coins, badge_name in milestones:
        if total_invites >= threshold:
            existing = await wander_coin_service._check_idempotency(
                db, "referral_milestone", threshold,
            )
            if not existing:
                tx_id = await _safe_grant_coins(
                    db, inviter_id, coins, "referral_reward",
                    "referral_milestone", threshold,
                    f"邀请阶梯 Lv{threshold} 奖励（{total_invites}人）",
                )
                if tx_id:
                    milestone_result: dict[str, Any] = {
                        "threshold": threshold,
                        "coin_tx_id": tx_id,
                        "amount": coins,
                    }
                    if badge_name:
                        milestone_result["badge"] = badge_name
                    return milestone_result
            break  # 只奖励当前达到的最高档

    return None


async def _check_repeat_violation(
    db: AsyncSession, user_id: int,
) -> dict[str, Any] | None:
    """检查30天内多次违规叠加惩罚（-150额外扣分）。

    30天内积分扣分次数 >=3 时触发，每月只惩罚一次。
    """
    from app.models.trust_level import PointRecord

    VIOLATION_REASONS = [
        "complaint_confirmed", "bad_speech", "violation_content",
        "spam_behavior", "harassment",
    ]

    now = datetime.now()
    thirty_days_ago = now - timedelta(days=30)

    result = await db.execute(
        select(func.count(PointRecord.id)).where(
            and_(
                PointRecord.user_id == user_id,
                PointRecord.points < 0,
                PointRecord.reason.in_(VIOLATION_REASONS),
                PointRecord.created_at >= thirty_days_ago,
            )
        )
    )
    violation_count = result.scalar() or 0

    if violation_count >= 3:
        period = now.year * 100 + now.month
        record_id = await _safe_add_points(
            db, user_id, -150, "repeat_violation",
            f"30天内{violation_count}次违规，额外惩罚",
            "repeat_violation", period,
        )
        if record_id:
            return {"point_record_id": record_id, "violation_count": violation_count}

    return None


# ---------------------------------------------------------------------------
# 新人任务奖励（P2-5）
# ---------------------------------------------------------------------------

async def on_newbie_task_complete(
    db: AsyncSession, user_id: int, task_code: str, ref_id: int | None = None,
) -> dict[str, Any] | None:
    """新人任务完成奖励。

    task_code:
        T1 - 完善个人资料（头像+昵称+bio）→ 晃晃币+10
        T2 - 发布首条评论 → 晃晃币+5
        T3 - 报名首个出游活动 → 晃晃币+50
        T4 - 邀请1位好友报名活动 → 晃晃币+30
        T5 - 发布首个出游活动 → 晃晃币+100

    幂等：ref_type=newbie_task, ref_id=task_num
    """
    TASK_REWARDS = {
        "T1": (10, "完善个人资料奖励"),
        "T2": (5, "发布首条评论奖励"),
        "T3": (50, "报名首个活动奖励"),
        "T4": (30, "邀请好友报名活动奖励"),
        "T5": (100, "发布首个活动奖励"),
    }

    if task_code not in TASK_REWARDS:
        logger.warning("未知的新人任务: %s", task_code)
        return None

    coins, remark = TASK_REWARDS[task_code]
    task_num = int(task_code[1])

    tx_id = await _safe_grant_coins(
        db, user_id, coins, "task_reward",
        "newbie_task", task_num,
        remark,
    )
    if tx_id:
        return {"task_code": task_code, "coin_tx_id": tx_id, "amount": coins}
    return None
