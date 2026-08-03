"""申诉相关 API 接口"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_admin_user
from app.db.session import get_db_session
from app.models.user import User
from app.services import appeal_service

router = APIRouter(prefix="/me", tags=["appeal"])


# ===== Request/Response Schemas =====

class TrustScoreAppealRequest(BaseModel):
    record_id: int = Field(..., description="信誉分变动记录ID")
    appeal_reason: str = Field(..., min_length=10, max_length=500, description="申诉理由")


class PointAppealRequest(BaseModel):
    record_id: int = Field(..., description="积分变动记录ID")
    appeal_reason: str = Field(..., min_length=10, max_length=500, description="申诉理由")


class AppealReviewRequest(BaseModel):
    approved: bool = Field(..., description="是否通过申诉")
    review_comment: str | None = Field(None, max_length=500, description="审核意见")


# ===== 信誉分申诉 =====

@router.post("/trust-score/appeal")
async def create_trust_appeal(
    req: TrustScoreAppealRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """创建信誉分申诉"""
    try:
        appeal = await appeal_service.create_trust_score_appeal(
            db=db,
            user_id=current_user.id,
            record_id=req.record_id,
            appeal_reason=req.appeal_reason,
        )
        await db.commit()
        return {
            "code": 0,
            "message": "申诉已提交，我们将在3个工作日内处理",
            "data": {
                "appeal_id": appeal.id,
                "status": appeal.status,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===== 积分申诉 =====

@router.post("/level/appeal")
async def create_point_appeal(
    req: PointAppealRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """创建积分申诉"""
    try:
        appeal = await appeal_service.create_point_appeal(
            db=db,
            user_id=current_user.id,
            record_id=req.record_id,
            appeal_reason=req.appeal_reason,
        )
        await db.commit()
        return {
            "code": 0,
            "message": "申诉已提交，我们将在3个工作日内处理",
            "data": {
                "appeal_id": appeal.id,
                "status": appeal.status,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===== 管理后台：审核申诉 =====

admin_router = APIRouter(prefix="/admin/appeals", tags=["admin-appeal"])


@admin_router.post("/trust-score/{appeal_id}/review")
async def review_trust_appeal(
    appeal_id: int,
    req: AppealReviewRequest,
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
):
    """审核信誉分申诉（管理员）"""
    try:
        appeal = await appeal_service.review_trust_score_appeal(
            db=db,
            appeal_id=appeal_id,
            reviewer_id=admin_user.id,
            approved=req.approved,
            review_comment=req.review_comment,
        )
        await db.commit()
        return {
            "code": 0,
            "message": "审核完成",
            "data": {
                "appeal_id": appeal.id,
                "status": appeal.status,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@admin_router.post("/point/{appeal_id}/review")
async def review_point_appeal(
    appeal_id: int,
    req: AppealReviewRequest,
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
):
    """审核积分申诉（管理员）"""
    try:
        appeal = await appeal_service.review_point_appeal(
            db=db,
            appeal_id=appeal_id,
            reviewer_id=admin_user.id,
            approved=req.approved,
            review_comment=req.review_comment,
        )
        await db.commit()
        return {
            "code": 0,
            "message": "审核完成",
            "data": {
                "appeal_id": appeal.id,
                "status": appeal.status,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
