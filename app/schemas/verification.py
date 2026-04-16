from datetime import datetime

from pydantic import BaseModel


class VerificationData(BaseModel):
    status: str
    rejectReason: str | None = None
    submittedAt: datetime | None = None
    reviewedAt: datetime | None = None


class SubmitVerificationRequest(BaseModel):
    realName: str
    idCardNumber: str
    faceVerifyToken: str | None = None

