"""用户生成内容审核：本地敏感词 + 联系方式 + 微信内容安全 API。"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from app.models.user import User
from app.schemas.activity import SendMessageRequest
from app.services.contact_content_filter import contact_text_blocked_reason
from app.services.sensitive_content_filter import sensitive_text_blocked_reason
from app.services.wechat_content_security import (
    CONTENT_VIOLATION_MESSAGE,
    SCENE_SOCIAL,
    media_check_async,
    msg_sec_check_text,
)
from app.services.wechat_miniapp import WechatLoginError

logger = logging.getLogger(__name__)


async def assert_text_content_safe(
    user: User,
    text: str | None,
    *,
    scene: int,
    contact_check: bool = True,
    strict: bool = False,
) -> None:
    raw = (text or "").strip()
    if not raw:
        return
    blocked = sensitive_text_blocked_reason(raw, strict=strict)
    if not blocked and contact_check:
        blocked = contact_text_blocked_reason(raw)
    if blocked:
        raise HTTPException(status_code=400, detail=CONTENT_VIOLATION_MESSAGE)
    try:
        await msg_sec_check_text(content=raw, openid=user.mp_openid, scene=scene)
    except WechatLoginError:
        logger.warning("wx content sec unavailable user_id=%s", user.id, exc_info=True)


async def assert_text_fields_safe(
    user: User,
    fields: dict[str, str | None],
    *,
    scene: int,
    contact_check: bool = True,
    strict: bool = False,
) -> None:
    for value in fields.values():
        await assert_text_content_safe(
            user,
            value,
            scene=scene,
            contact_check=contact_check,
            strict=strict,
        )


async def assert_image_urls_safe(
    user: User,
    urls: list[str] | None,
    *,
    scene: int = SCENE_SOCIAL,
) -> None:
    for url in urls or []:
        u = (url or "").strip()
        if u:
            await media_check_async(media_url=u, openid=user.mp_openid, scene=scene)


async def moderate_send_message_request(
    user: User,
    payload: SendMessageRequest,
    *,
    strict: bool = False,
) -> None:
    msg_type = payload.msgType
    if msg_type == "text":
        await assert_text_content_safe(user, payload.text, scene=SCENE_SOCIAL, strict=strict)
    elif msg_type == "location":
        await assert_text_fields_safe(
            user,
            {
                "locationName": payload.locationName,
                "address": payload.address,
            },
            scene=SCENE_SOCIAL,
            strict=strict,
        )
    elif msg_type == "image" and payload.imageUrl:
        await assert_image_urls_safe(user, [payload.imageUrl], scene=SCENE_SOCIAL)
    elif msg_type == "chain_signup":
        await assert_text_fields_safe(
            user,
            {
                "chainTitle": payload.chainTitle,
                "chainDescription": payload.chainDescription,
                "chainNote": payload.chainNote,
            },
            scene=SCENE_SOCIAL,
            strict=strict,
        )
