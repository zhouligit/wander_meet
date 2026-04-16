from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.notification import Notification
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.notification import (
    NotificationItem,
    NotificationListData,
    NotificationReadAllData,
    NotificationReadData,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    read: str = Query("all"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[NotificationListData]:
    filters = [Notification.user_id == current_user.id]
    if read == "unread":
        filters.append(Notification.read_at.is_(None))
    total = (await db.execute(select(func.count(Notification.id)).where(*filters))).scalar_one()
    rows = (
        (
            await db.execute(
                select(Notification)
                .where(*filters)
                .order_by(Notification.id.desc())
                .offset((page - 1) * pageSize)
                .limit(pageSize)
            )
        )
        .scalars()
        .all()
    )
    return APIResponse(
        data=NotificationListData(
            list=[
                NotificationItem(
                    notificationId=f"ntf_{n.id}",
                    type=n.type,
                    title=n.title,
                    body=n.body,
                    payload=n.payload_json,
                    readAt=n.read_at,
                    createdAt=n.created_at,
                )
                for n in rows
            ],
            total=total,
            page=page,
            pageSize=pageSize,
        )
    )


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[NotificationReadData]:
    nid = _parse_notification_id(notification_id)
    notification = await db.scalar(
        select(Notification).where(Notification.id == nid, Notification.user_id == current_user.id)
    )
    if not notification:
        return APIResponse(code=404, message="notification not found", data=NotificationReadData(notificationId=f"ntf_{nid}", readAt=datetime.now(UTC)))
    now = datetime.now(UTC)
    notification.read_at = now
    await db.commit()
    return APIResponse(data=NotificationReadData(notificationId=f"ntf_{nid}", readAt=now))


@router.post("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[NotificationReadAllData]:
    rows = (
        (
            await db.execute(
                select(Notification).where(
                    Notification.user_id == current_user.id, Notification.read_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for row in rows:
        row.read_at = now
    await db.commit()
    return APIResponse(data=NotificationReadAllData(updatedCount=len(rows)))


def _parse_notification_id(notification_id: str) -> int:
    if notification_id.startswith("ntf_"):
        notification_id = notification_id[4:]
    if not notification_id.isdigit():
        raise HTTPException(status_code=400, detail="Invalid notification id")
    return int(notification_id)

