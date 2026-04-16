from datetime import datetime

from pydantic import BaseModel


class BlockCreateRequest(BaseModel):
    blockedUserId: str


class BlockData(BaseModel):
    blockedUserId: str


class BlockListItem(BaseModel):
    blockedUserId: str
    nickname: str
    avatarUrl: str | None = None
    createdAt: datetime


class BlockListData(BaseModel):
    list: list[BlockListItem]

