"""按客户端 IP 固定窗口限流（依赖 ``X-Forwarded-For`` 首跳）。"""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.core.config import get_settings
from app.db.session import redis_client


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def enforce_auth_ip_rate_limit(request: Request, bucket: str) -> None:
    """
    bucket: ``sms_send`` | ``sms_login`` | ``wechat_login`` | ``email_register`` | ``email_login`` | ``email_forgot``
    每分钟计数；limit<=0 表示关闭。
    """
    settings = get_settings()
    if bucket == "sms_send":
        limit = settings.auth_sms_ip_limit_per_minute
    elif bucket == "sms_login":
        limit = settings.auth_login_ip_limit_per_minute
    elif bucket == "wechat_login":
        limit = settings.auth_wechat_login_ip_limit_per_minute
    elif bucket == "email_register":
        limit = settings.auth_email_register_ip_limit_per_minute
    elif bucket == "email_login":
        limit = settings.auth_email_login_ip_limit_per_minute
    elif bucket == "email_forgot":
        limit = settings.auth_email_forgot_ip_limit_per_minute
    else:
        limit = 0
    if limit <= 0:
        return

    ip = client_ip(request)
    key = f"wm:rl:ip:{ip}:{bucket}"
    n = await redis_client.incr(key)
    if n == 1:
        await redis_client.expire(key, 60)
    if n > limit:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
