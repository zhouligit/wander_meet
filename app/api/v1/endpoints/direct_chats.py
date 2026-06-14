from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.direct_message import DirectMessage
from app.models.dm_request import DmRequest
from app.models.dm_thread import DmThread
from app.models.dm_thread_read import DmThreadRead
from app.models.notification import Notification
from app.models.user import User
from app.schemas.activity import ChatMessageSender, SendMessageRequest
from app.schemas.common import APIResponse
from app.services.content_moderation import (
    assert_text_content_safe,
    assert_text_fields_safe,
    moderate_send_message_request,
)
from app.services.user_profile import assert_user_profile_complete
from app.services.wechat_content_security import SCENE_COMMENT, SCENE_PROFILE, SCENE_SOCIAL
from app.services.chat_message_payload import build_message_row_content
from app.services.chat_location import chat_last_message_preview, message_content_fields
from app.services.dm_relationship import (
    NOT_FRIENDS_MESSAGE,
    are_dm_peers_mutually_connected,
    clear_thread_removals,
    either_blocked,
    get_thread_by_users,
    is_activity_participant,
    is_thread_visible_for_user,
    peer_user_id,
    remove_thread_for_user,
    sort_user_pair,
    user_considers_peer_connected,
    visible_thread_filter,
)
from app.schemas.direct_chat import (
    AcceptDmRequestData,
    CreateDmRequestBody,
    DmRequestCreatedData,
    DmRequestItem,
    DmRequestListData,
    DirectChatContextData,
    DirectMessageItem,
    DirectMessagesData,
    MyDirectChatItem,
    MyDirectChatsData,
)

router = APIRouter(tags=["direct-chats"])


def _parse_activity_id_param(activity_id: str) -> int:
    s = activity_id[4:] if activity_id.startswith("act_") else activity_id
    if not s.isdigit():
        raise HTTPException(status_code=400, detail="Invalid activity id")
    return int(s)


def _parse_dmreq_id(s: str) -> int:
    t = s[6:] if s.startswith("dmreq_") else s
    if not t.isdigit():
        raise HTTPException(status_code=400, detail="Invalid request id")
    return int(t)


def _parse_dmthr_id(s: str) -> int:
    t = s[6:] if s.startswith("dmthr_") else s
    if not t.isdigit():
        raise HTTPException(status_code=400, detail="Invalid thread id")
    return int(t)


def _parse_dmmsg_id(s: str) -> int:
    t = s[6:] if s.startswith("dmmsg_") else s
    if not t.isdigit():
        raise HTTPException(status_code=400, detail="Invalid message id")
    return int(t)


def _uid_str(uid: int) -> str:
    return f"u_{uid}"


def _sender(u: User) -> ChatMessageSender:
    return ChatMessageSender(
        userId=_uid_str(u.id), nickname=u.nickname, avatarUrl=u.avatar_url
    )


def _sender_or_fallback(u: User | None, user_id: int) -> ChatMessageSender:
    if u is not None:
        return _sender(u)
    return ChatMessageSender(userId=_uid_str(user_id), nickname="用户", avatarUrl=None)


async def _assert_thread_member(thread: DmThread, user_id: int) -> None:
    if user_id not in (thread.user_low_id, thread.user_high_id):
        raise HTTPException(status_code=403, detail="Not a participant of this thread")


def _peer_id(thread: DmThread, user_id: int) -> int:
    return peer_user_id(thread, user_id)


async def _assert_thread_accessible(
    db: AsyncSession, thread: DmThread, user_id: int
) -> None:
    await _assert_thread_member(thread, user_id)
    if not await is_thread_visible_for_user(db, user_id, thread):
        raise HTTPException(status_code=403, detail="Friendship removed or blocked")


@router.post("/activities/{activity_id}/dm-requests")
async def create_dm_request(
    activity_id: str,
    payload: CreateDmRequestBody,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[DmRequestCreatedData]:
    assert_user_profile_complete(current_user)
    activity_pk = _parse_activity_id_param(activity_id)
    to_uid_s = payload.toUserId.strip()
    if to_uid_s.startswith("u_"):
        to_uid_s = to_uid_s[2:]
    if not to_uid_s.isdigit():
        return APIResponse(code=400, message="invalid toUserId", data=DmRequestCreatedData())
    to_user_id = int(to_uid_s)

    if to_user_id == current_user.id:
        return APIResponse(
            code=400, message="cannot request yourself", data=DmRequestCreatedData()
        )

    target = await db.scalar(select(User).where(User.id == to_user_id))
    if not target or target.status != "active":
        return APIResponse(code=404, message="user not found", data=DmRequestCreatedData())

    if not await is_activity_participant(db, activity_pk, current_user.id):
        return APIResponse(code=403, message="not an activity participant", data=DmRequestCreatedData(status=""))
    if not await is_activity_participant(db, activity_pk, to_user_id):
        return APIResponse(code=403, message="target not in activity", data=DmRequestCreatedData(status=""))

    if await either_blocked(db, current_user.id, to_user_id):
        return APIResponse(code=403, message="blocked", data=DmRequestCreatedData(status=""))

    from app.services.growth_trust import can_initiate_dm

    if not await can_initiate_dm(db, current_user.id):
        return APIResponse(
            code=403,
            message="trust score too low to start new chat",
            data=DmRequestCreatedData(status=""),
        )

    existing_thread = await get_thread_by_users(db, current_user.id, to_user_id)
    if existing_thread and await are_dm_peers_mutually_connected(
        db, current_user.id, to_user_id
    ):
        return APIResponse(
            code=409,
            message="already connected",
            data=DmRequestCreatedData(
                status="accepted",
                threadId=f"dmthr_{existing_thread.id}",
            ),
        )

    rev_pending = await db.scalar(
        select(DmRequest).where(
            DmRequest.from_user_id == to_user_id,
            DmRequest.to_user_id == current_user.id,
            DmRequest.status == "pending",
        )
    )
    if rev_pending:
        return APIResponse(
            code=409,
            message="incoming request exists",
            data=DmRequestCreatedData(
                requestId=f"dmreq_{rev_pending.id}", status="pending"
            ),
        )

    dup_out = await db.scalar(
        select(DmRequest).where(
            DmRequest.from_user_id == current_user.id,
            DmRequest.to_user_id == to_user_id,
            DmRequest.status == "pending",
        )
    )
    if dup_out:
        return APIResponse(
            code=409,
            message="request already sent",
            data=DmRequestCreatedData(requestId=f"dmreq_{dup_out.id}", status="pending"),
        )

    intro_raw = (payload.introText or "").strip()[:500]
    if intro_raw:
        await assert_text_content_safe(current_user, intro_raw, scene=SCENE_SOCIAL)
    intro = intro_raw or None
    req = DmRequest(
        activity_id=activity_pk,
        from_user_id=current_user.id,
        to_user_id=to_user_id,
        intro_text=intro,
        status="pending",
    )
    db.add(req)
    await db.flush()

    db.add(
        Notification(
            user_id=to_user_id,
            type="dm_request",
            title="好友申请",
            body=f"{current_user.nickname} 申请加你为好友",
            payload_json={
                "dmRequestId": f"dmreq_{req.id}",
                "activityId": f"act_{activity_pk}",
                "fromUserId": _uid_str(current_user.id),
            },
        )
    )
    await db.commit()

    return APIResponse(
        data=DmRequestCreatedData(requestId=f"dmreq_{req.id}", status="pending")
    )


@router.get("/me/dm-requests")
async def list_dm_requests(
    direction: str = Query("incoming", pattern="^(incoming|outgoing)$"),
    status: str = Query("pending", pattern="^(pending|all)$"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[DmRequestListData]:
    filters = []
    if direction == "incoming":
        filters.append(DmRequest.to_user_id == current_user.id)
    else:
        filters.append(DmRequest.from_user_id == current_user.id)
    if status == "pending":
        filters.append(DmRequest.status == "pending")

    total = (
        await db.execute(select(func.count(DmRequest.id)).where(*filters))
    ).scalar_one()

    rows = (
        (
            await db.execute(
                select(DmRequest)
                .where(*filters)
                .order_by(DmRequest.id.desc())
                .offset((page - 1) * pageSize)
                .limit(pageSize)
            )
        )
        .scalars()
        .all()
    )

    user_ids: set[int] = set()
    for r in rows:
        user_ids.add(r.from_user_id)
        user_ids.add(r.to_user_id)
    users_map: dict[int, User] = {}
    if user_ids:
        ur = await db.execute(select(User).where(User.id.in_(user_ids)))
        users_map = {u.id: u for u in ur.scalars().all()}

    items: list[DmRequestItem] = []
    for r in rows:
        fu = users_map.get(r.from_user_id)
        tu = users_map.get(r.to_user_id)
        items.append(
            DmRequestItem(
                requestId=f"dmreq_{r.id}",
                activityId=f"act_{r.activity_id}",
                fromUser=_sender_or_fallback(fu, r.from_user_id),
                toUser=_sender_or_fallback(tu, r.to_user_id),
                introText=r.intro_text,
                status=r.status,
                threadId=(f"dmthr_{r.thread_id}" if r.thread_id else None),
                createdAt=r.created_at,
                respondedAt=r.responded_at,
            )
        )

    return APIResponse(
        data=DmRequestListData(list=items, total=total, page=page, pageSize=pageSize)
    )


@router.post("/me/dm-requests/{request_id}/accept")
async def accept_dm_request(
    request_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[AcceptDmRequestData]:
    rid = _parse_dmreq_id(request_id)
    req = await db.scalar(select(DmRequest).where(DmRequest.id == rid))
    if not req:
        return APIResponse(code=404, message="request not found", data=AcceptDmRequestData(requestId="", threadId="", status=""))
    if req.to_user_id != current_user.id:
        return APIResponse(code=403, message="not your request", data=AcceptDmRequestData(requestId="", threadId="", status=""))
    if req.status != "pending":
        return APIResponse(code=400, message="request not pending", data=AcceptDmRequestData(requestId="", threadId="", status=req.status))

    if await either_blocked(db, req.from_user_id, req.to_user_id):
        return APIResponse(code=403, message="blocked", data=AcceptDmRequestData(requestId="", threadId="", status=""))

    low, high = sort_user_pair(req.from_user_id, req.to_user_id)
    thread = await db.scalar(
        select(DmThread).where(
            DmThread.user_low_id == low, DmThread.user_high_id == high
        )
    )
    if not thread:
        thread = DmThread(user_low_id=low, user_high_id=high)
        db.add(thread)
        await db.flush()
    else:
        await clear_thread_removals(db, thread.id)

    now = datetime.now(UTC)
    req.status = "accepted"
    req.thread_id = thread.id
    req.responded_at = now
    thread.updated_at = now

    from_user = await db.scalar(select(User).where(User.id == req.from_user_id))
    if from_user:
        db.add(
            Notification(
                user_id=req.from_user_id,
                type="dm_request_accepted",
                title="已成为好友",
                body=f"{current_user.nickname} 已同意你的好友申请",
                payload_json={
                    "dmRequestId": f"dmreq_{req.id}",
                    "threadId": f"dmthr_{thread.id}",
                    "toUserId": _uid_str(current_user.id),
                },
            )
        )

    await db.commit()

    return APIResponse(
        data=AcceptDmRequestData(
            requestId=f"dmreq_{req.id}",
            threadId=f"dmthr_{thread.id}",
            status="accepted",
        )
    )


@router.post("/me/dm-requests/{request_id}/reject")
async def reject_dm_request(
    request_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict[str, str]]:
    rid = _parse_dmreq_id(request_id)
    req = await db.scalar(select(DmRequest).where(DmRequest.id == rid))
    if not req:
        return APIResponse(code=404, message="request not found", data={"status": "not_found"})
    if req.to_user_id != current_user.id:
        return APIResponse(code=403, message="not your request", data={"status": "forbidden"})
    if req.status != "pending":
        return APIResponse(code=400, message="request not pending", data={"status": req.status})

    req.status = "rejected"
    req.responded_at = datetime.now(UTC)
    await db.commit()
    return APIResponse(data={"status": "rejected"})


@router.delete("/me/dm-requests/{request_id}")
async def cancel_dm_request(
    request_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict[str, str]]:
    rid = _parse_dmreq_id(request_id)
    req = await db.scalar(select(DmRequest).where(DmRequest.id == rid))
    if not req:
        return APIResponse(code=404, message="request not found", data={"status": "not_found"})
    if req.from_user_id != current_user.id:
        return APIResponse(code=403, message="not your request", data={"status": "forbidden"})
    if req.status != "pending":
        return APIResponse(code=400, message="request not pending", data={"status": req.status})

    req.status = "cancelled"
    req.responded_at = datetime.now(UTC)
    await db.commit()
    return APIResponse(data={"status": "cancelled"})


@router.get("/me/direct-chats")
async def my_direct_chats(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MyDirectChatsData]:
    uid = current_user.id
    vis_filter = visible_thread_filter(uid)

    total = (
        await db.execute(select(func.count(DmThread.id)).where(vis_filter))
    ).scalar_one()

    threads = (
        (
            await db.execute(
                select(DmThread)
                .where(vis_filter)
                .order_by(DmThread.updated_at.desc(), DmThread.id.desc())
                .offset((page - 1) * pageSize)
                .limit(pageSize)
            )
        )
        .scalars()
        .all()
    )
    if not threads:
        return APIResponse(
            data=MyDirectChatsData(list=[], total=total, page=page, pageSize=pageSize)
        )

    thread_ids = [t.id for t in threads]
    peer_ids = [_peer_id(t, uid) for t in threads]
    peers = (
        await db.execute(select(User).where(User.id.in_(peer_ids)))
    ).scalars().all()
    peer_map = {u.id: u for u in peers}

    latest_id_subq = (
        select(DirectMessage.thread_id.label("tid"), func.max(DirectMessage.id).label("mid"))
        .where(DirectMessage.thread_id.in_(thread_ids))
        .group_by(DirectMessage.thread_id)
        .subquery()
    )
    latest_rows = await db.execute(
        select(DirectMessage).join(
            latest_id_subq,
            and_(
                DirectMessage.thread_id == latest_id_subq.c.tid,
                DirectMessage.id == latest_id_subq.c.mid,
            ),
        )
    )
    latest_by_tid = {m.thread_id: m for m in latest_rows.scalars().all()}

    unread_rows = await db.execute(
        select(DirectMessage.thread_id, func.count(DirectMessage.id))
        .outerjoin(
            DmThreadRead,
            and_(
                DmThreadRead.thread_id == DirectMessage.thread_id,
                DmThreadRead.user_id == uid,
            ),
        )
        .where(
            DirectMessage.thread_id.in_(thread_ids),
            DirectMessage.sender_id != uid,
            DirectMessage.id > func.coalesce(DmThreadRead.last_read_message_id, 0),
        )
        .group_by(DirectMessage.thread_id)
    )
    unread_map = {tid: c for tid, c in unread_rows.all()}

    items: list[MyDirectChatItem] = []
    for t in threads:
        peer_id = _peer_id(t, uid)
        pu = peer_map.get(peer_id)
        if not pu:
            continue
        lm = latest_by_tid.get(t.id)
        last_message = None
        last_at = None
        if lm:
            last_at = lm.created_at
            last_message = chat_last_message_preview(
                lm.msg_type, lm.text_content, lm.image_url
            )
        items.append(
            MyDirectChatItem(
                threadId=f"dmthr_{t.id}",
                peerUserId=_uid_str(pu.id),
                peerNickname=pu.nickname,
                peerAvatarUrl=pu.avatar_url,
                lastMessage=last_message,
                lastMessageAt=last_at,
                unreadCount=int(unread_map.get(t.id, 0)),
            )
        )

    return APIResponse(
        data=MyDirectChatsData(list=items, total=total, page=page, pageSize=pageSize)
    )


@router.delete("/me/direct-chats/{thread_id}")
async def remove_direct_chat_friend(
    thread_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict[str, bool]]:
    """删除好友：对当前用户隐藏私聊会话，可再次申请私聊恢复。"""
    tid = _parse_dmthr_id(thread_id)
    thread = await db.scalar(select(DmThread).where(DmThread.id == tid))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    await _assert_thread_member(thread, current_user.id)
    await remove_thread_for_user(db, current_user.id, thread)
    await db.commit()
    return APIResponse(data={"ok": True})


@router.get("/direct-chats/{thread_id}/context")
async def get_direct_chat_context(
    thread_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[DirectChatContextData]:
    tid = _parse_dmthr_id(thread_id)
    thread = await db.scalar(select(DmThread).where(DmThread.id == tid))
    if not thread:
        return APIResponse(
            code=404,
            message="thread not found",
            data=DirectChatContextData(
                threadId=thread_id,
                peerUserId="",
                canSendMessage=False,
                statusMessage=NOT_FRIENDS_MESSAGE,
            ),
        )
    await _assert_thread_member(thread, current_user.id)
    peer = _peer_id(thread, current_user.id)
    visible = await is_thread_visible_for_user(db, current_user.id, thread)
    mutual = await are_dm_peers_mutually_connected(db, current_user.id, peer)
    can_send = visible and mutual
    return APIResponse(
        data=DirectChatContextData(
            threadId=f"dmthr_{tid}",
            peerUserId=_uid_str(peer),
            canSendMessage=can_send,
            statusMessage=None if can_send else NOT_FRIENDS_MESSAGE,
        )
    )


@router.get("/direct-chats/{thread_id}/messages")
async def list_direct_messages(
    thread_id: str,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[DirectMessagesData]:
    tid = _parse_dmthr_id(thread_id)
    thread = await db.scalar(select(DmThread).where(DmThread.id == tid))
    if not thread:
        return APIResponse(code=404, message="thread not found", data=DirectMessagesData(list=[], nextCursor=None))
    await _assert_thread_accessible(db, thread, current_user.id)

    stmt = (
        select(DirectMessage, User)
        .join(User, User.id == DirectMessage.sender_id)
        .where(DirectMessage.thread_id == tid)
    )
    if cursor:
        cid = _parse_dmmsg_id(cursor)
        stmt = stmt.where(DirectMessage.id < cid)
    stmt = stmt.order_by(DirectMessage.id.desc()).limit(limit)
    rows = (await db.execute(stmt)).all()
    rows = list(reversed(rows))

    items = [
        DirectMessageItem(
            messageId=f"dmmsg_{msg.id}",
            threadId=f"dmthr_{tid}",
            sender=_sender(user),
            msgType=msg.msg_type,
            **message_content_fields(msg.msg_type, msg.text_content, msg.image_url),
            createdAt=msg.created_at,
        )
        for msg, user in rows
    ]
    next_cursor = f"dmmsg_{rows[0][0].id}" if rows else None
    return APIResponse(data=DirectMessagesData(list=items, nextCursor=next_cursor))


@router.post("/direct-chats/{thread_id}/messages")
async def send_direct_message(
    thread_id: str,
    payload: SendMessageRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[DirectMessageItem]:
    tid = _parse_dmthr_id(thread_id)
    thread = await db.scalar(select(DmThread).where(DmThread.id == tid))
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    assert_user_profile_complete(current_user)
    await _assert_can_send_direct_message(db, thread, current_user.id)

    await moderate_send_message_request(current_user, payload)
    msg_type, text_content, image_url = build_message_row_content(
        payload, current_user.id, nickname=current_user.nickname
    )

    msg = DirectMessage(
        thread_id=tid,
        sender_id=current_user.id,
        msg_type=msg_type,
        text_content=text_content,
        image_url=image_url,
    )
    db.add(msg)
    thread.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(msg)

    return APIResponse(
        data=DirectMessageItem(
            messageId=f"dmmsg_{msg.id}",
            threadId=f"dmthr_{tid}",
            sender=_sender(current_user),
            msgType=msg.msg_type,
            **message_content_fields(msg.msg_type, msg.text_content, msg.image_url),
            createdAt=msg.created_at or datetime.now(UTC),
        )
    )


@router.patch("/direct-chats/{thread_id}/read")
async def mark_direct_read(
    thread_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict[str, int]]:
    tid = _parse_dmthr_id(thread_id)
    thread = await db.scalar(select(DmThread).where(DmThread.id == tid))
    if not thread:
        return APIResponse(code=404, message="thread not found", data={"updatedCount": 0})
    await _assert_thread_accessible(db, thread, current_user.id)

    last_msg_id = await db.scalar(
        select(func.max(DirectMessage.id)).where(DirectMessage.thread_id == tid)
    )
    last_msg_id = int(last_msg_id or 0)

    row = await db.scalar(
        select(DmThreadRead).where(
            DmThreadRead.user_id == current_user.id, DmThreadRead.thread_id == tid
        )
    )
    if row:
        row.last_read_message_id = last_msg_id
    else:
        db.add(
            DmThreadRead(
                user_id=current_user.id,
                thread_id=tid,
                last_read_message_id=last_msg_id,
            )
        )
    await db.commit()
    return APIResponse(data={"updatedCount": 1})
