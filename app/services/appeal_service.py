"""信誉分和积分申诉服务层"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appeal import PointAppeal, TrustScoreAppeal
from app.models.trust_level import PointRecord, TrustScoreRecord
from app.services.trust_score import record_trust_score_change
from app.services.user_level import add_points


async def create_trust_score_appeal(
    db: AsyncSession,
    user_id: int,
    record_id: int,
    appeal_reason: str,
) -> TrustScoreAppeal:
    """创建信誉分申诉"""
    # 验证记录存在且属于该用户
    result = await db.execute(
        select(TrustScoreRecord).where(
            TrustScoreRecord.id == record_id,
            TrustScoreRecord.user_id == user_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise ValueError("信誉分变动记录不存在或不属于当前用户")

    # 检查是否已有待处理的申诉
    existing = await db.execute(
        select(TrustScoreAppeal).where(
            TrustScoreAppeal.record_id == record_id,
            TrustScoreAppeal.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("该记录已有待处理的申诉")

    appeal = TrustScoreAppeal(
        user_id=user_id,
        record_id=record_id,
        appeal_reason=appeal_reason,
    )
    db.add(appeal)
    await db.flush()
    return appeal


async def review_trust_score_appeal(
    db: AsyncSession,
    appeal_id: int,
    reviewer_id: int,
    approved: bool,
    review_comment: Optional[str] = None,
) -> TrustScoreAppeal:
    """审核信誉分申诉"""
    result = await db.execute(
        select(TrustScoreAppeal).where(TrustScoreAppeal.id == appeal_id)
    )
    appeal = result.scalar_one_or_none()
    if not appeal:
        raise ValueError("申诉记录不存在")
    if appeal.status != "pending":
        raise ValueError("申诉已处理")

    appeal.status = "approved" if approved else "rejected"
    appeal.reviewer_id = reviewer_id
    appeal.review_comment = review_comment
    appeal.reviewed_at = datetime.now()

    # 如果申诉通过，恢复信誉分
    if approved:
        record_result = await db.execute(
            select(TrustScoreRecord).where(TrustScoreRecord.id == appeal.record_id)
        )
        record = record_result.scalar_one_or_none()
        if record:
            # 反向调整信誉分
            change = -record.change
            await record_trust_score_change(
                db,
                user_id=record.user_id,
                change=change,
                reason="appeal_approved",
                reason_detail="申诉通过，恢复信誉分",
                ref_type="appeal",
                ref_id=appeal.id,
            )

    await db.flush()
    return appeal


async def create_point_appeal(
    db: AsyncSession,
    user_id: int,
    record_id: int,
    appeal_reason: str,
) -> PointAppeal:
    """创建积分申诉"""
    # 验证记录存在且属于该用户
    result = await db.execute(
        select(PointRecord).where(
            PointRecord.id == record_id,
            PointRecord.user_id == user_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise ValueError("积分变动记录不存在或不属于当前用户")

    # 检查是否已有待处理的申诉
    existing = await db.execute(
        select(PointAppeal).where(
            PointAppeal.record_id == record_id,
            PointAppeal.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("该记录已有待处理的申诉")

    appeal = PointAppeal(
        user_id=user_id,
        record_id=record_id,
        appeal_reason=appeal_reason,
    )
    db.add(appeal)
    await db.flush()
    return appeal


async def review_point_appeal(
    db: AsyncSession,
    appeal_id: int,
    reviewer_id: int,
    approved: bool,
    review_comment: Optional[str] = None,
) -> PointAppeal:
    """审核积分申诉"""
    result = await db.execute(
        select(PointAppeal).where(PointAppeal.id == appeal_id)
    )
    appeal = result.scalar_one_or_none()
    if not appeal:
        raise ValueError("申诉记录不存在")
    if appeal.status != "pending":
        raise ValueError("申诉已处理")

    appeal.status = "approved" if approved else "rejected"
    appeal.reviewer_id = reviewer_id
    appeal.review_comment = review_comment
    appeal.reviewed_at = datetime.now()

    # 如果申诉通过，恢复积分
    if approved:
        record_result = await db.execute(
            select(PointRecord).where(PointRecord.id == appeal.record_id)
        )
        record = record_result.scalar_one_or_none()
        if record:
            # 反向调整积分
            points = -record.points
            await add_points(
                db,
                user_id=record.user_id,
                points=points,
                reason="appeal_approved",
                reason_detail="申诉通过，恢复积分",
                ref_type="appeal",
                ref_id=appeal.id,
            )

    await db.flush()
    return appeal
