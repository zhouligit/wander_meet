"""信誉分与等级 API 接口"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.services.trust_score import (
    get_trust_score_summary,
    get_trust_score_history,
)
from app.services.user_level import (
    get_user_level_info,
    get_point_history,
)
from app.core.level_config import get_user_privileges

router = APIRouter(prefix="/me", tags=["trust-level"])


@router.get("/trust-score")
async def get_trust_score(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """获取信誉分摘要"""
    summary = await get_trust_score_summary(db, current_user.id)
    return {"code": 0, "message": "success", "data": summary}


@router.get("/trust-score/history")
async def get_trust_score_history_api(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """获取信誉分变动历史"""
    history = await get_trust_score_history(db, current_user.id, limit, offset)
    
    items = [
        {
            "id": record.id,
            "change": record.change,
            "trust_score_before": record.trust_score_before,
            "trust_score_after": record.trust_score_after,
            "reason": record.reason,
            "reason_detail": record.reason_detail,
            "ref_type": record.ref_type,
            "ref_id": record.ref_id,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }
        for record in history
    ]
    
    return {"code": 0, "message": "success", "data": items}


@router.get("/level")
async def get_level(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """获取用户等级信息"""
    level_info = await get_user_level_info(db, current_user.id)
    return {"code": 0, "message": "success", "data": level_info}


@router.get("/level/history")
async def get_level_history_api(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """获取积分变动历史"""
    history = await get_point_history(db, current_user.id, limit, offset)
    
    items = [
        {
            "id": record.id,
            "points": record.points,
            "points_before": record.points_before,
            "points_after": record.points_after,
            "reason": record.reason,
            "reason_detail": record.reason_detail,
            "ref_type": record.ref_type,
            "ref_id": record.ref_id,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }
        for record in history
    ]
    
    return {"code": 0, "message": "success", "data": items}


@router.get("/level/privileges")
async def get_level_privileges(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """获取用户等级权益信息"""
    level_info = await get_user_level_info(db, current_user.id)
    level_code = level_info["level_code"]
    
    privileges = get_user_privileges(level_code)
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "level_code": level_code,
            "level_name": level_info["level_name"],
            **privileges,
        }
    }
