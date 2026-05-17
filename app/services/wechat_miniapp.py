"""微信小程序 ``wx.login`` → ``jscode2session``。"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


class WechatLoginError(Exception):
    """微信登录失败（配置、code 无效或微信侧错误）。"""


@dataclass(frozen=True)
class WechatSession:
    openid: str
    session_key: str | None
    unionid: str | None


def mock_openid_from_code(code: str) -> str:
    """测试用：同一 code 稳定映射为 openid。"""
    digest = hashlib.sha256(f"wm-mock:{code}".encode("utf-8")).hexdigest()[:28]
    return f"mock_{digest}"


async def code_to_session(code: str) -> WechatSession:
    settings = get_settings()
    raw_code = (code or "").strip()
    if not raw_code:
        raise WechatLoginError("code is required")

    if settings.wx_mp_use_mock:
        oid = mock_openid_from_code(raw_code)
        logger.info("wx_mp_use_mock: openid suffix=%s", oid[-6:])
        return WechatSession(openid=oid, session_key=None, unionid=None)

    appid = (settings.wx_mp_appid or "").strip()
    secret = (settings.wx_mp_appsecret or "").strip()
    if not appid or not secret:
        raise WechatLoginError("WeChat mini program is not configured")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _CODE2SESSION_URL,
                params={
                    "appid": appid,
                    "secret": secret,
                    "js_code": raw_code,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.exception("jscode2session HTTP failed")
        raise WechatLoginError("WeChat service unavailable") from exc

    errcode = data.get("errcode", 0)
    if errcode:
        errmsg = data.get("errmsg") or "unknown"
        logger.warning("jscode2session errcode=%s errmsg=%s", errcode, errmsg)
        raise WechatLoginError("Invalid or expired WeChat login code")

    openid = (data.get("openid") or "").strip()
    if not openid:
        raise WechatLoginError("WeChat response missing openid")

    unionid = (data.get("unionid") or "").strip() or None
    session_key = (data.get("session_key") or "").strip() or None
    return WechatSession(openid=openid, session_key=session_key, unionid=unionid)
