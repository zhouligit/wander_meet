"""晃晃币(WanderCoin)服务层

并发安全：grant_coins / spend_coins 均使用 SELECT FOR UPDATE 行锁。
幂等校验：grant_coins 基于 ref_type + ref_id 防重复发放。
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wander_coin import WanderCoinWallet, WanderCoinTransaction

logger = logging.getLogger(__name__)


async def get_or_create_wallet(
    db: AsyncSession, user_id: int, *, for_update: bool = False
) -> WanderCoinWallet:
    """获取或创建用户钱包。

    Args:
        for_update: True 时加行锁（SELECT FOR UPDATE），用于写操作。
    """
    stmt = select(WanderCoinWallet).where(WanderCoinWallet.user_id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    wallet = result.scalar_one_or_none()

    if not wallet:
        wallet = WanderCoinWallet(
            user_id=user_id,
            balance=0,
            total_earned=0,
            total_spent=0,
            frozen_amount=0,
        )
        db.add(wallet)
        await db.flush()

    return wallet


async def _check_idempotency(
    db: AsyncSession, user_id: int, ref_type: str, ref_id: int
) -> WanderCoinTransaction | None:
    """基于 user_id + ref_type + ref_id 检查是否已存在交易记录（幂等校验）。

    返回已存在的交易记录（表示重复请求），或 None（表示首次请求）。
    """
    result = await db.execute(
        select(WanderCoinTransaction).where(
            and_(
                WanderCoinTransaction.user_id == user_id,
                WanderCoinTransaction.ref_type == ref_type,
                WanderCoinTransaction.ref_id == ref_id,
            )
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def grant_coins(
    db: AsyncSession,
    user_id: int,
    amount: int,
    tx_type: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
    remark: str | None = None,
) -> WanderCoinTransaction:
    """
    发放晃晃币
    - amount: 正数
    - SELECT FOR UPDATE 保证并发安全
    - ref_type + ref_id 幂等校验防重复发放
    - 自动创建钱包（如果不存在）
    - 记录交易流水
    """
    # 幂等校验：同一 ref_type + ref_id 不重复发放
    if ref_type and ref_id is not None:
        existing = await _check_idempotency(db, ref_type, ref_id)
        if existing:
            logger.info(
                "晃晃币幂等拦截: ref_type=%s ref_id=%s 已存在 tx_id=%s",
                ref_type, ref_id, existing.id,
            )
            return existing

    # 加锁获取钱包
    wallet = await get_or_create_wallet(db, user_id, for_update=True)

    wallet.balance += amount
    wallet.total_earned += amount
    balance_after = wallet.balance

    tx = WanderCoinTransaction(
        user_id=user_id,
        amount=amount,
        balance_after=balance_after,
        tx_type=tx_type,
        ref_type=ref_type,
        ref_id=ref_id,
        remark=remark,
    )
    db.add(tx)
    await db.flush()

    return tx


async def spend_coins(
    db: AsyncSession,
    user_id: int,
    amount: int,
    tx_type: str,
    ref_type: str | None = None,
    ref_id: int | None = None,
    remark: str | None = None,
) -> WanderCoinTransaction | None:
    """
    消费晃晃币
    - amount: 正数（实际扣减金额）
    - SELECT FOR UPDATE 保证并发安全
    - 余额不足时返回 None
    - 记录交易流水
    """
    wallet = await get_or_create_wallet(db, user_id, for_update=True)

    if wallet.balance < amount:
        return None

    wallet.balance -= amount
    wallet.total_spent += amount
    balance_after = wallet.balance

    tx = WanderCoinTransaction(
        user_id=user_id,
        amount=-amount,  # 支出为负数
        balance_after=balance_after,
        tx_type=tx_type,
        ref_type=ref_type,
        ref_id=ref_id,
        remark=remark,
    )
    db.add(tx)
    await db.flush()

    return tx


async def get_wallet_info(db: AsyncSession, user_id: int) -> dict:
    """获取钱包信息"""
    wallet = await get_or_create_wallet(db, user_id)
    return {
        "balance": wallet.balance,
        "total_earned": wallet.total_earned,
        "total_spent": wallet.total_spent,
        "frozen_amount": wallet.frozen_amount,
    }


async def get_transactions(
    db: AsyncSession,
    user_id: int,
    tx_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """
    获取交易流水
    - 支持按 tx_type 筛选
    - 返回分页结果，含关联来源标题
    """
    # 构建查询条件
    conditions = [WanderCoinTransaction.user_id == user_id]
    if tx_type:
        conditions.append(WanderCoinTransaction.tx_type == tx_type)
    
    # 查询总数
    count_query = select(func.count(WanderCoinTransaction.id)).where(*conditions)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 查询流水列表
    query = (
        select(WanderCoinTransaction)
        .where(*conditions)
        .order_by(desc(WanderCoinTransaction.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    transactions = list(result.scalars().all())
    
    # 批量获取关联来源标题（避免 N+1）
    ref_titles = await _batch_resolve_ref_titles(db, transactions)
    
    # 格式化返回
    items = []
    for tx in transactions:
        item = {
            "id": tx.id,
            "amount": tx.amount,
            "balance_after": tx.balance_after,
            "tx_type": tx.tx_type,
            "ref_type": tx.ref_type,
            "ref_id": tx.ref_id,
            "remark": tx.remark,
            "ref_title": ref_titles.get(tx.id),
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
        }
        items.append(item)
    
    return {
        "total": total,
        "items": items,
    }


async def _batch_resolve_ref_titles(
    db: AsyncSession, transactions: list[WanderCoinTransaction]
) -> dict[int, str | None]:
    """批量解析交易关联的来源标题，返回 {tx_id: title}"""
    from app.models.activity import Activity

    # 按 ref_type 分组收集 ref_id
    activity_ids: set[int] = set()
    for tx in transactions:
        if tx.ref_type == "activity" and tx.ref_id:
            activity_ids.add(tx.ref_id)
    
    # 批量查询活动标题
    activity_map: dict[int, str] = {}
    if activity_ids:
        result = await db.execute(
            select(Activity.id, Activity.title).where(Activity.id.in_(activity_ids))
        )
        activity_map = {row[0]: row[1] for row in result.all()}
    
    # 组装结果
    titles: dict[int, str | None] = {}
    for tx in transactions:
        if tx.ref_type == "activity" and tx.ref_id and tx.ref_id in activity_map:
            titles[tx.id] = activity_map[tx.ref_id]
        else:
            titles[tx.id] = None
    
    return titles
