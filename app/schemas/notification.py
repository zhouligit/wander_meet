from datetime import datetime

from pydantic import BaseModel


class NotificationItem(BaseModel):
    notificationId: str
    type: str
    title: str
    body: str
    payload: dict | None = None
    readAt: datetime | None = None
    createdAt: datetime


class NotificationListData(BaseModel):
    list: list[NotificationItem]
    total: int
    page: int
    pageSize: int


class NotificationReadData(BaseModel):
    notificationId: str
    readAt: datetime


class NotificationReadAllData(BaseModel):
    updatedCount: int

