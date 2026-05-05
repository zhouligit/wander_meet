from pydantic import BaseModel, Field


class UserPublicProfileData(BaseModel):
    """对外展示的用户资料（查看他人主页 / 发起人详情）。"""

    userId: str
    nickname: str
    avatarUrl: str | None = None
    bio: str = ""
    tags: list[str] = Field(default_factory=list)
    verificationBadge: bool = False
    organizedCount: int = 0
