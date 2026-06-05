from pydantic import BaseModel, Field

from app.schemas.city_group import CityHostBadgeItem


class UserPublicProfileData(BaseModel):
    """对外展示的用户资料（查看他人主页 / 发起人详情）。"""

    userId: str
    nickname: str
    avatarUrl: str | None = None
    gender: str | None = None
    bio: str = ""
    tags: list[str] = Field(default_factory=list)
    verificationBadge: bool = False
    organizedCount: int = 0
    trustLevel: str | None = None
    photoVerified: bool = False
    meetCount: int = 0
    showMeetCount: bool = True
    badges: list[str] = Field(default_factory=list)
    premiumBadge: bool = False
    cityHostBadges: list[CityHostBadgeItem] = Field(default_factory=list)


class UserDmContextData(BaseModel):
    """在当前活动群语境下，与目标用户的私聊关系（用于发起申请前展示按钮状态）。"""

    threadId: str | None = None
    outgoingPendingRequestId: str | None = None
    incomingPendingRequestId: str | None = None
    canRequest: bool
    denyReason: str | None = None
