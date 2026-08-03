"""用户等级服务层"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, desc, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trust_level import UserLevel, PointRecord
from app.core.level_config import get_level_by_points, get_next_level


async def get_or_create_user_level(
    db: AsyncSession, user_id: int, *, for_update: bool = False
) -> UserLevel:
    """获取或创建用户等级记录。

    Args:
        for_update: True 时加行锁（SELECT FOR UPDATE），用于写操作。
    """
    stmt = select(UserLevel).where(UserLevel.user_id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    user_level = result.scalar_one_or_none()
    
    if not user_level:
        user_level = UserLevel(user_id=user_id, total_points=0)
        db.add(user_level)
        await db.flush()
    
    return user_level


async def add_points(
    db: AsyncSession,
    user_id: int,
    points: int,
    reason: str,
    reason_detail: str = "",
    ref_type: Optional[str] = None,
    ref_id: Optional[int] = None,
) -> PointRecord:
    """增加用户积分"""
    user_level = await get_or_create_user_level(db, user_id, for_update=True)
    
    points_before = user_level.total_points
    points_after = max(0, points_before + points)
    
    # 创建变动记录
    record = PointRecord(
        user_id=user_id,
        points=points,
        points_before=points_before,
        points_after=points_after,
        reason=reason,
        reason_detail=reason_detail,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    db.add(record)
    
    # 更新积分和等级
    user_level.total_points = points_after
    level_code, level_name = get_level_by_points(points_after)
    user_level.level_code = level_code
    user_level.level_name = level_name
    user_level.updated_at = datetime.now()
    
    await db.flush()
    return record


async def get_user_level_info(db: AsyncSession, user_id: int) -> dict:
    """获取用户等级信息"""
    user_level = await get_or_create_user_level(db, user_id)
    next_level = get_next_level(user_level.total_points)
    
    return {
        "total_points": user_level.total_points,
        "level_code": user_level.level_code,
        "level_name": user_level.level_name,
        "next_level": next_level,
    }


async def get_point_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[PointRecord]:
    """获取积分变动历史"""
    result = await db.execute(
        select(PointRecord)
        .where(PointRecord.user_id == user_id)
        .order_by(desc(PointRecord.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def check_daily_login_bonus(db: AsyncSession, user_id: int) -> bool:
    """检查并发放每日登录积分奖励"""
    # 检查今日是否已发放
    today = datetime.now().date()
    result = await db.execute(
        select(func.count(PointRecord.id)).where(
            and_(
                PointRecord.user_id == user_id,
                PointRecord.reason == "daily_login",
                func.date(PointRecord.created_at) == today,
            )
        )
    )
    count = result.scalar() or 0
    
    if count > 0:
        return False  # 今日已发放
    
    # 发放每日登录奖励
    await add_points(
        db=db,
        user_id=user_id,
        points=2,
        reason="daily_login",
        reason_detail="每日登录奖励",
    )
    
    # 检查连续登录奖励
    await check_login_streak_bonus(db, user_id)
    
    return True


async def check_login_streak_bonus(db: AsyncSession, user_id: int) -> None:
    """检查并发放连续登录奖励（7天+20，30天+100）"""
    # 查询最近的 daily_login 记录，按日期去重
    recent_logins = await db.execute(
        select(func.date(PointRecord.created_at))
        .where(
            and_(
                PointRecord.user_id == user_id,
                PointRecord.reason == "daily_login",
            )
        )
        .order_by(desc(func.date(PointRecord.created_at)))
        .limit(30)
    )
    login_dates = sorted([row[0] for row in recent_logins.all()], reverse=True)
    
    if len(login_dates) < 2:
        return
    
    # 计算连续天数（从今天往前数）
    today = datetime.now().date()
    streak = 0
    check_date = today
    for login_date in login_dates:
        if login_date == check_date:
            streak += 1
            check_date = check_date - __import__('datetime').timedelta(days=1)
        else:
            break
    
    # 发放连续登录奖励
    if streak >= 30:
        # 检查30天奖励是否已发放
        existing = await db.execute(
            select(func.count(PointRecord.id)).where(
                and_(
                    PointRecord.user_id == user_id,
                    PointRecord.reason == "login_streak_30",
                    func.date(PointRecord.created_at) == today,
                )
            )
        )
        if (existing.scalar() or 0) == 0:
            await add_points(
                db=db,
                user_id=user_id,
                points=100,
                reason="login_streak_30",
                reason_detail=f"连续登录30天奖励",
            )
    elif streak >= 7:
        # 检查7天奖励是否已发放
        existing = await db.execute(
            select(func.count(PointRecord.id)).where(
                and_(
                    PointRecord.user_id == user_id,
                    PointRecord.reason == "login_streak_7",
                    func.date(PointRecord.created_at) == today,
                )
            )
        )
        if (existing.scalar() or 0) == 0:
            await add_points(
                db=db,
                user_id=user_id,
                points=20,
                reason="login_streak_7",
                reason_detail=f"连续登录7天奖励",
            )
