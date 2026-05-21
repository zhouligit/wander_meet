"""微信小程序：``jscode2session``、``access_token``、手机号快速验证。"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.db.session import redis_client

logger = logging.getLogger(__name__)

_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
_PHONE_URL = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"
_ACCESS_TOKEN_REDIS_KEY = "wm:wx:mp_access_token"


class WechatLoginError(Exception):
    """微信 API 调用失败（配置、code 无效或微信侧错误）。"""


@dataclass(frozen=True)
class WechatSession:
    openid: str
    session_key: str | None
    unionid: str | None


def mock_openid_from_code(code: str) -> str:
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
        logger.warning("jscode2session errcode=%s errmsg=%s", errcode, data.get("errmsg"))
        raise WechatLoginError("Invalid or expired WeChat login code")

    openid = (data.get("openid") or "").strip()
    if not openid:
        raise WechatLoginError("WeChat response missing openid")

    unionid = (data.get("unionid") or "").strip() or None
    session_key = (data.get("session_key") or "").strip() or None
    return WechatSession(openid=openid, session_key=session_key, unionid=unionid)


async def _fetch_access_token(appid: str, secret: str) -> tuple[str, int]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            _TOKEN_URL,
            params={"grant_type": "client_credential", "appid": appid, "secret": secret},
        )
        resp.raise_for_status()
        data = resp.json()
    if data.get("errcode"):
        raise WechatLoginError(data.get("errmsg") or "Failed to get WeChat access_token")
    token = (data.get("access_token") or "").strip()
    expires_in = int(data.get("expires_in") or 7200)
    if not token:
        raise WechatLoginError("WeChat access_token missing")
    return token, expires_in


async def invalidate_mp_access_token() -> None:
    """清除缓存的 ``access_token``（微信返回 40001/42001 时重试换号用）。"""
    try:
        await redis_client.delete(_ACCESS_TOKEN_REDIS_KEY)
    except Exception:
        logger.warning("failed to delete wx mp access_token cache key", exc_info=True)


async def get_mp_access_token(*, force_refresh: bool = False) -> str:
    settings = get_settings()
    if settings.wx_mp_use_mock:
        return "mock_mp_access_token"

    if not force_refresh:
        cached = await redis_client.get(_ACCESS_TOKEN_REDIS_KEY)
        if cached:
            return cached

    appid = (settings.wx_mp_appid or "").strip()
    secret = (settings.wx_mp_appsecret or "").strip()
    if not appid or not secret:
        raise WechatLoginError("WeChat mini program is not configured")

    token, expires_in = await _fetch_access_token(appid, secret)
    ttl = max(60, expires_in - 120)
    await redis_client.set(_ACCESS_TOKEN_REDIS_KEY, token, ex=ttl)
    return token


# 微信 access_token 失效时需换新 token 再调一次手机号接口
_MP_TOKEN_INVALID_ERRCODES = frozenset({40001, 40014, 42001})


def mock_phone_from_code(code: str) -> str:
    """Mock：由 phoneCode 稳定生成 11 位测试号（非真实下发）。"""
    n = int(hashlib.sha256(f"wm-mock-phone:{code}".encode()).hexdigest()[:8], 16) % 9000000000
    return f"1{1000000000 + n}"[:11]


async def get_phone_number_from_code(phone_code: str) -> str:
    """小程序 ``getPhoneNumber`` 返回的 code → 纯手机号（大陆 11 位）。"""
    settings = get_settings()
    raw = (phone_code or "").strip()
    if not raw:
        raise WechatLoginError("phoneCode is required")

    if settings.wx_mp_use_mock:
        return mock_phone_from_code(raw)

    data: dict = {}
    for attempt in range(2):
        access_token = await get_mp_access_token(force_refresh=attempt > 0)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{_PHONE_URL}?access_token={access_token}",
                    json={"code": raw},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.exception("getuserphonenumber HTTP failed")
            raise WechatLoginError("WeChat phone service unavailable") from exc

        errcode = int(data.get("errcode") or 0)
        if errcode in _MP_TOKEN_INVALID_ERRCODES and attempt == 0:
            logger.warning(
                "getuserphonenumber token invalid errcode=%s, refreshing access_token",
                errcode,
            )
            await invalidate_mp_access_token()
            continue
        if errcode:
            logger.warning("getuserphonenumber errcode=%s errmsg=%s", errcode, data.get("errmsg"))
            if errcode == 40029:
                raise WechatLoginError("微信手机号凭证已失效，请重新点击授权")
            raise WechatLoginError("Invalid or expired WeChat phone code")
        break

    info = data.get("phone_info") or {}
    if isinstance(info, str):
        try:
            info = json.loads(info)
        except json.JSONDecodeError:
            info = {}
    pure = (info.get("purePhoneNumber") or info.get("phoneNumber") or "").strip()
    digits = "".join(c for c in pure if c.isdigit())
    if len(digits) >= 11:
        return digits[-11:]
    raise WechatLoginError("WeChat did not return a valid phone number")
