"""抖音/字节小程序：``jscode2session``（tt.login 的 code）。"""

from __future__ import annotations

import hashlib
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_CODE2SESSION_URL = "https://developer.toutiao.com/api/apps/v2/jscode2session"

# 见 https://developer.open-douyin.com/docs/.../code-2-session
_DY_ERR_MESSAGES: dict[int, str] = {
    40015: "Douyin appid 错误（检查 DY_MP_APPID 是否与小程序 AppID 一致）",
    40017: "Douyin secret 错误（检查 DY_MP_APPSECRET 是否为开发设置里的 App Secret）",
    40018: "Douyin login code 无效（常见：服务器 appid 与开发者工具不一致，或 code 已用过）",
    40019: "Douyin anonymous_code 无效",
}


class DouyinLoginError(Exception):
    """抖音 code2session 失败。"""


class DouyinSession:
    __slots__ = ("openid", "session_key", "unionid")

    def __init__(self, openid: str, session_key: str | None, unionid: str | None) -> None:
        self.openid = openid
        self.session_key = session_key
        self.unionid = unionid


def mock_openid_from_code(code: str) -> str:
    digest = hashlib.sha256(f"wm-dy-mock:{code}".encode("utf-8")).hexdigest()[:28]
    return f"dy_mock_{digest}"


async def code_to_session(code: str) -> DouyinSession:
    settings = get_settings()
    raw_code = (code or "").strip()
    if not raw_code:
        raise DouyinLoginError("code is required")

    if settings.dy_mp_use_mock:
        oid = mock_openid_from_code(raw_code)
        logger.info("dy_mp_use_mock: openid suffix=%s", oid[-6:])
        return DouyinSession(openid=oid, session_key=None, unionid=None)

    appid = (settings.dy_mp_appid or "").strip()
    secret = (settings.dy_mp_appsecret or "").strip()
    if not appid or not secret:
        raise DouyinLoginError("Douyin mini program is not configured")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _CODE2SESSION_URL,
                json={
                    "appid": appid,
                    "secret": secret,
                    "code": raw_code,
                },
            )
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError as exc:
        logger.exception("douyin jscode2session HTTP failed")
        raise DouyinLoginError("Douyin service unavailable") from exc

    err_no = body.get("err_no", 0)
    if err_no not in (0, None):
        tips = body.get("err_tips") or body.get("message") or "unknown"
        logger.warning(
            "douyin jscode2session err_no=%s tips=%s appid_suffix=%s",
            err_no,
            tips,
            (appid[-6:] if len(appid) >= 6 else appid),
        )
        msg = _DY_ERR_MESSAGES.get(int(err_no)) if err_no is not None else None
        if not msg:
            msg = f"Douyin login failed (err_no={err_no}, {tips})"
        raise DouyinLoginError(msg)

    data = body.get("data") or {}
    if not isinstance(data, dict):
        raise DouyinLoginError("Douyin response invalid")

    openid = (data.get("openid") or "").strip()
    if not openid:
        raise DouyinLoginError("Douyin response missing openid")

    unionid = (data.get("unionid") or "").strip() or None
    session_key = (data.get("session_key") or "").strip() or None
    return DouyinSession(openid=openid, session_key=session_key, unionid=unionid)
