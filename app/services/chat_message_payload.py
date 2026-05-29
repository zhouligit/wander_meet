"""聊天发消息：校验与 DB 字段映射。"""

from __future__ import annotations

from fastapi import HTTPException

from app.schemas.activity import SendMessageRequest
from app.services.bos_storage import BosNotConfiguredError, validate_stored_chat_image_url
from app.services.chat_stickers import validate_sticker_id
from app.services.contact_content_filter import contact_text_blocked_reason


def build_message_row_content(
    payload: SendMessageRequest, user_id: int
) -> tuple[str, str | None, str | None]:
    """校验发送体，返回 (msg_type, text_content, image_url) 写入数据库。"""
    msg_type = payload.msgType
    if msg_type not in {"text", "image", "sticker"}:
        raise HTTPException(status_code=400, detail="Unsupported msgType")

    text_content: str | None = None
    image_url: str | None = None

    if msg_type == "text":
        if not payload.text:
            raise HTTPException(status_code=400, detail="text is required for text message")
        blocked = contact_text_blocked_reason(payload.text)
        if blocked:
            raise HTTPException(status_code=400, detail=blocked)
        text_content = payload.text
    elif msg_type == "image":
        if not payload.imageUrl:
            raise HTTPException(status_code=400, detail="imageUrl is required for image message")
        try:
            image_url = validate_stored_chat_image_url(payload.imageUrl, user_id)
        except BosNotConfiguredError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    else:
        text_content = validate_sticker_id(payload.stickerId or "")

    return msg_type, text_content, image_url
