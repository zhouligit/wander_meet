from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from app.schemas.activity import ChatMessageSender
from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z


class CreateDmRequestBody(BaseModel):
    toUserId: str = Field(..., description="对方用户 u_*")
    introText: str | None = Field(None, max_length=500)


class DmRequestItem(BaseModel):
    requestId: str
    activityId: str
    fromUser: ChatMessageSender
    toUser: ChatMessageSender
    introText: str | None
    status: str
    threadId: str | None = None
    createdAt: datetime
    respondedAt: datetime | None = None

    @field_serializer("createdAt", "respondedAt")
    def _ser_times(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z(v)


class DmRequestListData(BaseModel):
    list: list[DmRequestItem]
    total: int
    page: int
    pageSize: int


class DmRequestCreatedData(BaseModel):
    requestId: str = ""
    threadId: str | None = None
    status: str = ""


class AcceptDmRequestData(BaseModel):
    requestId: str = ""
    threadId: str = ""
    status: str = ""


class DirectMessageItem(BaseModel):
    messageId: str
    threadId: str
    sender: ChatMessageSender
    msgType: str
    text: str | None = None
    imageUrl: str | None = None
    createdAt: datetime

    @field_serializer("createdAt")
    def _ser_created_at(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z(v) or ""


class DirectMessagesData(BaseModel):
    list: list[DirectMessageItem]
    nextCursor: str | None = None


class MyDirectChatItem(BaseModel):
    threadId: str
    peerUserId: str
    peerNickname: str
    peerAvatarUrl: str | None = None
    lastMessage: str | None = None
    lastMessageAt: datetime | None = None
    unreadCount: int

    @field_serializer("lastMessageAt")
    def _ser_last_at(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z(v)


class MyDirectChatsData(BaseModel):
    list: list[MyDirectChatItem]
    total: int
    page: int
    pageSize: int
