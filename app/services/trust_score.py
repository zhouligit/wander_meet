"""信誉分服务层"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trust_level import TrustScoreRecord
from app.models.growth_trust import UserTrustProfile


# 信誉分等级映射
TRUST_LEVELS = [
    (0, 200, "信用较差", "trust_poor"),
    (200, 400, "信用一般", "trust_fair"),
    (400, 600, "信用良好", "trust_good"),
    (600, 800, "信用优秀", "trust_excellent"),
    (800, 1001, "信用极好", "trust_outstanding"),
]


def get_trust_level(score: int) -> tuple[str, str]:
    """根据分数获取信誉等级"""
    for min_score, max_score, level_name, level_code in TRUST_LEVELS:
        if min_score <= score < max_score:
            return level_name, level_code
    return "信用一般", "trust_fair"


async def record_trust_score_change(
    db: AsyncSession,
    user_id: int,
    change: int,
    reason: str,
    reason_detail: str = "",
    ref_type: Optional[str] = None,
    ref_id: Optional[int] = None,
) -> TrustScoreRecord:
    """记录信誉分变动"""
    # 获取或创建信任档案（加行锁防并发）
    result = await db.execute(
        select(UserTrustProfile)
        .where(UserTrustProfile.user_id == user_id)
        .with_for_update()
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        profile = UserTrustProfile(
            user_id=user_id,
            trust_score=500,  # 初始信誉分
        )
        db.add(profile)
        await db.flush()
    
    score_before = profile.trust_score
    score_after = max(0, min(1000, score_before + change))

    # 创建变动记录
    record = TrustScoreRecord(
        user_id=user_id,
        change=change,
        trust_score_before=score_before,
        trust_score_after=score_after,
        reason=reason,
        reason_detail=reason_detail,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    db.add(record)
    
    # 更新信誉分
    profile.trust_score = score_after
    profile.updated_at = datetime.now()
    
    await db.flush()
    return record


async def get_trust_score_summary(db: AsyncSession, user_id: int) -> dict:
    """获取信誉分摘要"""
    result = await db.execute(
        select(UserTrustProfile).where(UserTrustProfile.user_id == user_id)
    )
    trust_profile = result.scalar_one_or_none()
    
    if not trust_profile:
        return {
            "trust_score": 500,
            "level_name": "信用一般",
            "level_code": "trust_fair",
            "meet_count": 0,
            "photo_verified": False,
        }
    
    level_name, level_code = get_trust_level(trust_profile.trust_score)
    
    return {
        "trust_score": trust_profile.trust_score,
        "level_name": level_name,
        "level_code": level_code,
        "meet_count": trust_profile.meet_count or 0,
        "photo_verified": trust_profile.photo_verified or False,
    }


async def get_trust_score_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[TrustScoreRecord]:
    """获取信誉分变动历史"""
    result = await db.execute(
        select(TrustScoreRecord)
        .where(TrustScoreRecord.user_id == user_id)
        .order_by(desc(TrustScoreRecord.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
