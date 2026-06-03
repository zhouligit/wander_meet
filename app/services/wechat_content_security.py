"""微信小程序内容安全：``security.msgSecCheck`` / ``mediaCheckAsync``。"""

from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException

from app.core.config import get_settings
from app.services.wechat_miniapp import (
    WechatLoginError,
    _MP_TOKEN_INVALID_ERRCODES,
    get_mp_access_token,
    invalidate_mp_access_token,
)

logger = logging.getLogger(__name__)

_MSG_SEC_CHECK_URL = "https://api.weixin.qq.com/wxa/msg_sec_check"
_MEDIA_CHECK_ASYNC_URL = "https://api.weixin.qq.com/wxa/media_check_async"

# 微信审核要求：仅提示用户内容违规，不暴露技术细节
CONTENT_VIOLATION_MESSAGE = "所发布内容含违规信息，请修改后重试"

# scene：1 资料 2 评论 3 论坛 4 社交日志
SCENE_PROFILE = 1
SCENE_COMMENT = 2
SCENE_FORUM = 3
SCENE_SOCIAL = 4

_CONTENT_RISKY_ERRCODES = frozenset({87014, 61024})


async def _post_wechat_json(url: str, body: dict) -> dict:
    data: dict = {}
    for attempt in range(2):
        access_token = await get_mp_access_token(force_refresh=attempt > 0)
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(f"{url}?access_token={access_token}", json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.exception("wechat content sec HTTP failed url=%s", url)
            raise WechatLoginError("WeChat content security service unavailable") from exc

        errcode = int(data.get("errcode") or 0)
        if errcode in _MP_TOKEN_INVALID_ERRCODES and attempt == 0:
            await invalidate_mp_access_token()
            continue
        return data
    return data


def _raise_if_unsafe_msg_sec_response(data: dict) -> None:
    errcode = int(data.get("errcode") or 0)
    if errcode in _CONTENT_RISKY_ERRCODES:
        raise HTTPException(status_code=400, detail=CONTENT_VIOLATION_MESSAGE)
    if errcode:
        logger.warning("msg_sec_check errcode=%s errmsg=%s", errcode, data.get("errmsg"))
        return

    result = data.get("result") or {}
    suggest = str(result.get("suggest") or "").strip().lower()
    if suggest in {"risky", "review"}:
        raise HTTPException(status_code=400, detail=CONTENT_VIOLATION_MESSAGE)


async def msg_sec_check_text(*, content: str, openid: str | None, scene: int) -> None:
    """调用微信文本内容安全；违规时 ``HTTPException(400)``。"""
    text = (content or "").strip()
    if not text:
        return

    settings = get_settings()
    if not settings.wx_content_sec_enabled or settings.wx_mp_use_mock:
        return
    if not (settings.wx_mp_appid or "").strip() or not (settings.wx_mp_appsecret or "").strip():
        logger.warning("wx content sec skipped: mini program not configured")
        return

    openid_val = (openid or "").strip()
    if openid_val:
        body = {"openid": openid_val, "scene": scene, "version": 2, "content": text}
        data = await _post_wechat_json(_MSG_SEC_CHECK_URL, body)
        errcode = int(data.get("errcode") or 0)
        if errcode == 40003:
            # openid 无效时降级 v1（仅 content）
            data = await _post_wechat_json(_MSG_SEC_CHECK_URL, {"content": text})
        _raise_if_unsafe_msg_sec_response(data)
        return

    data = await _post_wechat_json(_MSG_SEC_CHECK_URL, {"content": text})
    _raise_if_unsafe_msg_sec_response(data)


async def media_check_async(*, media_url: str, openid: str | None, scene: int) -> None:
    """异步图片/音频审核（尽力调用；结果由微信回调，此处不阻塞发布）。"""
    url = (media_url or "").strip()
    if not url:
        return

    settings = get_settings()
    if not settings.wx_content_sec_enabled or settings.wx_mp_use_mock:
        return
    if not (settings.wx_mp_appid or "").strip():
        return

    openid_val = (openid or "").strip()
    if not openid_val:
        return

    body = {
        "openid": openid_val,
        "scene": scene,
        "version": 2,
        "media_url": url,
        "media_type": 2,
    }
    try:
        data = await _post_wechat_json(_MEDIA_CHECK_ASYNC_URL, body)
        errcode = int(data.get("errcode") or 0)
        if errcode:
            logger.warning(
                "media_check_async errcode=%s trace=%s",
                errcode,
                data.get("trace_id"),
            )
    except WechatLoginError:
        logger.warning("media_check_async skipped due to token error", exc_info=True)
