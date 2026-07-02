"""活动分享：微信小程序码（``getwxacodeunlimit``）。"""

from __future__ import annotations

import base64
import logging
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.core.config import get_settings
from app.db.session import redis_client
from app.services.wechat_miniapp import (
    WechatLoginError,
    get_mp_access_token,
    invalidate_mp_access_token,
)

logger = logging.getLogger(__name__)

_ACTIVITY_SHARE_SCENE_PREFIX = "id="
_ACTIVITY_SHARE_SCENE_LEGACY_PREFIX = "sa="
_ACTIVITY_SHARE_SCENE_PREFIXES = (_ACTIVITY_SHARE_SCENE_PREFIX, _ACTIVITY_SHARE_SCENE_LEGACY_PREFIX)
_ACTIVITY_SHARE_QRCODE_DEFAULT_PAGE = "pages/activity-detail/activity-detail"
_UNLIMITED_QRCODE_URL = "https://api.weixin.qq.com/wxa/getwxacodeunlimit"
_MP_TOKEN_INVALID_ERRCODES = frozenset({40001, 40014, 42001})


def build_activity_share_scene(activity_id: int) -> str:
    if activity_id <= 0:
        raise ValueError("invalid activity id")
    scene = f"{_ACTIVITY_SHARE_SCENE_PREFIX}{activity_id}"
    if len(scene) > 32:
        raise HTTPException(status_code=400, detail="活动 ID 过长，无法生成分享码")
    return scene


def parse_activity_share_scene(scene_raw: str | None) -> int | None:
    scene = (scene_raw or "").strip()
    if not scene:
        return None
    try:
        from urllib.parse import unquote

        scene = unquote(scene)
    except Exception:
        pass
    for prefix in _ACTIVITY_SHARE_SCENE_PREFIXES:
        if not scene.startswith(prefix):
            continue
        tail = scene[len(prefix) :].strip()
        if not tail.isdigit():
            return None
        return int(tail)
    return None


def _cache_key(activity_id: int) -> str:
    settings = get_settings()
    env = (settings.wx_mp_env_version or "release").strip()
    page = (
        settings.wx_mp_share_qrcode_page or _ACTIVITY_SHARE_QRCODE_DEFAULT_PAGE
    ).strip().lstrip("/")
    page_key = page.replace("/", ":")
    return f"wm:act_share_qr:{activity_id}:{env}:{page_key}"


async def _fetch_mock_qrcode_png(scene: str) -> bytes:
    url = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=430x430&data={quote(scene)}"
    )
    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def _fetch_wechat_qrcode_png(scene: str, page: str) -> bytes:
    settings = get_settings()
    env_version = (settings.wx_mp_env_version or "release").strip()
    check_path = env_version == "release"

    for attempt in range(2):
        access_token = await get_mp_access_token(force_refresh=attempt > 0)
        body = {
            "scene": scene,
            "page": page,
            "width": 430,
            "check_path": check_path,
            "env_version": env_version,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{_UNLIMITED_QRCODE_URL}?access_token={access_token}",
                    json=body,
                )
                resp.raise_for_status()
                raw = resp.content
        except httpx.HTTPError as exc:
            logger.exception("getwxacodeunlimit HTTP failed scene=%s", scene)
            raise WechatLoginError("WeChat QR code service unavailable") from exc

        if raw[:1] == b"{":
            try:
                data = resp.json()
            except Exception:
                data = {}
            errcode = int(data.get("errcode") or 0)
            if errcode in _MP_TOKEN_INVALID_ERRCODES and attempt == 0:
                await invalidate_mp_access_token()
                continue
            errmsg = (data.get("errmsg") or "Failed to create WeChat QR code").strip()
            logger.warning(
                "getwxacodeunlimit errcode=%s errmsg=%s scene=%s page=%s",
                errcode,
                errmsg,
                scene,
                page,
            )
            if errcode == 45009:
                raise HTTPException(
                    status_code=503,
                    detail="分享码生成次数已达上限，请稍后再试",
                )
            raise WechatLoginError(errmsg)

        if len(raw) < 128:
            raise WechatLoginError("WeChat QR code response invalid")
        return raw

    raise WechatLoginError("Failed to create WeChat QR code")


async def get_activity_share_qrcode_base64(activity_id: int) -> tuple[str, str]:
    """返回 ``(scene, image_base64)``；Redis 缓存 PNG。"""
    settings = get_settings()
    scene = build_activity_share_scene(activity_id)
    page = (
        settings.wx_mp_share_qrcode_page or _ACTIVITY_SHARE_QRCODE_DEFAULT_PAGE
    ).strip().lstrip("/")

    cache_key = _cache_key(activity_id)
    cached = await redis_client.get(cache_key)
    if cached:
        return scene, cached

    if settings.wx_mp_use_mock:
        png = await _fetch_mock_qrcode_png(scene)
    else:
        try:
            png = await _fetch_wechat_qrcode_png(scene, page)
        except WechatLoginError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    encoded = base64.b64encode(png).decode("ascii")
    ttl = max(3600, int(settings.activity_share_qrcode_cache_ttl_seconds or 604800))
    await redis_client.set(cache_key, encoded, ex=ttl)
    return scene, encoded
