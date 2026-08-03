"""晃晃币(WanderCoin) API 接口"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.services import wander_coin_service

router = APIRouter(prefix="/me", tags=["wander-coin"])


@router.get("/wallet")
async def get_wallet(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """获取晃晃币钱包信息"""
    wallet_info = await wander_coin_service.get_wallet_info(db, current_user.id)
    return {"code": 0, "message": "success", "data": wallet_info}


@router.get("/wallet/transactions")
async def get_wallet_transactions(
    tx_type: str | None = Query(None, description="交易类型筛选"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """获取晃晃币交易流水"""
    result = await wander_coin_service.get_transactions(
        db, current_user.id, tx_type=tx_type, limit=limit, offset=offset
    )
    return {"code": 0, "message": "success", "data": result}
