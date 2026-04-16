from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.models.user_verification import UserVerification
from app.schemas.common import APIResponse
from app.schemas.verification import (
    SubmitVerificationRequest,
    VerificationData,
)

router = APIRouter(prefix="/me/verification", tags=["verification"])


@router.get("")
async def get_verification(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[VerificationData]:
    record = await db.scalar(
        select(UserVerification)
        .where(UserVerification.user_id == current_user.id)
        .order_by(UserVerification.id.desc())
    )
    if not record:
        return APIResponse(data=VerificationData(status="none"))
    return APIResponse(
        data=VerificationData(
            status=record.status,
            rejectReason=record.reject_reason,
            submittedAt=record.submitted_at,
            reviewedAt=record.reviewed_at,
        )
    )


@router.post("")
async def submit_verification(
    payload: SubmitVerificationRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict[str, str]]:
    record = UserVerification(
        user_id=current_user.id,
        status="pending",
        real_name=payload.realName,
        id_card_number=payload.idCardNumber,
        face_verify_token=payload.faceVerifyToken,
        submitted_at=datetime.now(),
    )
    db.add(record)
    await db.commit()
    return APIResponse(data={"status": "pending"})

