from pydantic import BaseModel, Field


class PinActivityRequest(BaseModel):
    activity_id: int = Field(..., gt=0, description="活动 ID")
    hours: int = Field(24, ge=1, le=72, description="置顶时长（小时）")


class PurchaseBadgeRequest(BaseModel):
    badge_code: str = Field(..., min_length=1, max_length=32, description="徽章代码")


class PurchaseAvatarFrameRequest(BaseModel):
    frame_code: str = Field(..., min_length=1, max_length=32, description="头像框代码")


class CoinSpendResponse(BaseModel):
    coins_spent: int
    balance_after: int


class PinActivityData(CoinSpendResponse):
    activity_id: int
    pinned_until: str  # ISO 8601


class BadgePurchaseData(CoinSpendResponse):
    badge_code: str
    badge_id: int


class AvatarFramePurchaseData(CoinSpendResponse):
    frame_code: str
    entitlement_id: int
    expires_at: str  # ISO 8601
