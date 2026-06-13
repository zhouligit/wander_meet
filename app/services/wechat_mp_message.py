"""微信小程序消息推送：URL 验签（GET echostr / POST 回调）。"""

from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger(__name__)


def wechat_mp_msg_signature(token: str, timestamp: str, nonce: str) -> str:
    parts = sorted([token, timestamp, nonce])
    return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()


def verify_wechat_mp_msg_signature(
    token: str, signature: str, timestamp: str, nonce: str
) -> bool:
    tok = (token or "").strip()
    sig = (signature or "").strip()
    ts = (timestamp or "").strip()
    nc = (nonce or "").strip()
    if not tok or not sig or not ts or not nc:
        return False
    expected = wechat_mp_msg_signature(tok, ts, nc)
    ok = expected == sig
    if not ok:
        logger.warning(
            "wechat msg signature mismatch expected=%s got=%s ts=%s nonce=%s",
            expected,
            sig,
            ts,
            nc,
        )
    return ok
