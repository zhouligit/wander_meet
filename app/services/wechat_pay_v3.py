"""微信支付 APIv3：Native 扫码、小程序 JSAPI、回调验签解密。"""

from __future__ import annotations

import base64
import json
import logging
import secrets
import time
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings
from app.services.pay_common import yuan_to_fen

logger = logging.getLogger(__name__)

_API_BASE = "https://api.mch.weixin.qq.com"
_NATIVE_PATH = "/v3/pay/transactions/native"
_JSAPI_PATH = "/v3/pay/transactions/jsapi"

_platform_certs: dict[str, Any] = {}


class WeChatPayError(Exception):
    pass


def _load_private_key():
    settings = get_settings()
    pem = (settings.wechat_pay_private_key or "").strip()
    if not pem and settings.wechat_pay_private_key_path:
        path = Path(settings.wechat_pay_private_key_path)
        if path.is_file():
            pem = path.read_text(encoding="utf-8")
    if not pem:
        raise WeChatPayError("WeChat Pay merchant private key is not configured")
    return serialization.load_pem_private_key(pem.encode("utf-8"), password=None)


def _rsa_sign(message: str) -> str:
    key = _load_private_key()
    sig = key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode("ascii")


def _authorization(method: str, url_path: str, body: str) -> str:
    settings = get_settings()
    mch_id = (settings.wechat_pay_mch_id or "").strip()
    serial = (settings.wechat_pay_cert_serial or "").strip()
    if not mch_id or not serial:
        raise WeChatPayError("WeChat Pay mch_id or cert serial not configured")

    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    message = f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body}\n"
    signature = _rsa_sign(message)
    return (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{mch_id}",'
        f'nonce_str="{nonce}",signature="{signature}",'
        f'timestamp="{timestamp}",serial_no="{serial}"'
    )


async def _request_v3(
    method: str, url_path: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    body = ""
    if method.upper() != "GET" and payload is not None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    headers = {
        "Authorization": _authorization(method, url_path, body),
        "Accept": "application/json",
    }
    if body:
        headers["Content-Type"] = "application/json"
    url = f"{_API_BASE}{url_path}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.request(
                method, url, content=body.encode("utf-8") if body else None, headers=headers
            )
    except httpx.HTTPError as exc:
        logger.exception("WeChat Pay v3 HTTP failed path=%s", url_path)
        raise WeChatPayError("WeChat Pay request failed") from exc

    if resp.status_code >= 400:
        logger.warning("WeChat Pay v3 error status=%s body=%s", resp.status_code, resp.text[:500])
        raise WeChatPayError(f"WeChat Pay error: {resp.text[:200]}")

    if not resp.content:
        return {}
    return resp.json()


def _pay_payload(
    *,
    out_trade_no: str,
    description: str,
    attach: str,
    notify_url: str,
    total_fen: int,
    appid: str,
) -> dict[str, Any]:
    settings = get_settings()
    mch_id = (settings.wechat_pay_mch_id or "").strip()
    return {
        "appid": appid,
        "mchid": mch_id,
        "description": description,
        "out_trade_no": out_trade_no,
        "notify_url": notify_url,
        "attach": attach,
        "amount": {"total": total_fen, "currency": "CNY"},
    }


async def native_pay(
    *,
    out_trade_no: str,
    total_fee_yuan: str,
    description: str,
    attach: str,
    notify_url: str,
) -> str:
    settings = get_settings()
    if settings.wechat_pay_use_mock:
        return f"weixin://wxpay/bizpayurl?pr=mock_{out_trade_no[-12:]}"

    appid = (settings.wx_mp_appid or "").strip()
    if not appid:
        raise WeChatPayError("WX_MP_APPID not configured for Native pay")

    payload = _pay_payload(
        out_trade_no=out_trade_no,
        description=description,
        attach=attach,
        notify_url=notify_url,
        total_fen=yuan_to_fen(total_fee_yuan),
        appid=appid,
    )
    data = await _request_v3("POST", _NATIVE_PATH, payload)
    code_url = (data.get("code_url") or "").strip()
    if not code_url:
        raise WeChatPayError("WeChat Pay Native missing code_url")
    return code_url


async def jsapi_pay(
    *,
    out_trade_no: str,
    total_fee_yuan: str,
    description: str,
    attach: str,
    notify_url: str,
    openid: str,
) -> str:
    settings = get_settings()
    if settings.wechat_pay_use_mock:
        return f"mock_prepay_{out_trade_no[-16:]}"

    appid = (settings.wx_mp_appid or "").strip()
    if not appid:
        raise WeChatPayError("WX_MP_APPID not configured for JSAPI pay")

    payload = _pay_payload(
        out_trade_no=out_trade_no,
        description=description,
        attach=attach,
        notify_url=notify_url,
        total_fen=yuan_to_fen(total_fee_yuan),
        appid=appid,
    )
    payload["payer"] = {"openid": openid}
    data = await _request_v3("POST", _JSAPI_PATH, payload)
    prepay_id = (data.get("prepay_id") or "").strip()
    if not prepay_id:
        raise WeChatPayError("WeChat Pay JSAPI missing prepay_id")
    return prepay_id


def build_miniprogram_payment_params(prepay_id: str) -> dict[str, str]:
    """小程序 ``uni.requestPayment`` 参数。"""
    settings = get_settings()
    if settings.wechat_pay_use_mock:
        return {
            "timeStamp": str(int(time.time())),
            "nonceStr": secrets.token_hex(8),
            "package": f"prepay_id={prepay_id}",
            "signType": "RSA",
            "paySign": "mock_sign",
        }

    app_id = (settings.wx_mp_appid or "").strip()
    if not app_id:
        raise WeChatPayError("WX_MP_APPID not configured")

    timestamp = str(int(time.time()))
    nonce_str = secrets.token_hex(16)
    package = f"prepay_id={prepay_id}"
    message = f"{app_id}\n{timestamp}\n{nonce_str}\n{package}\n"
    pay_sign = _rsa_sign(message)
    return {
        "timeStamp": timestamp,
        "nonceStr": nonce_str,
        "package": package,
        "signType": "RSA",
        "paySign": pay_sign,
    }


async def _refresh_platform_certs() -> None:
    settings = get_settings()
    data = await _request_v3("GET", "/v3/certificates")
    for item in data.get("data") or []:
        serial = (item.get("serial_no") or "").strip()
        enc = item.get("encrypt_certificate") or {}
        if not serial or not enc:
            continue
        nonce = (enc.get("nonce") or "").encode("utf-8")
        aad = (enc.get("associated_data") or "").encode("utf-8")
        ciphertext = base64.b64decode(enc.get("ciphertext") or "")
        key = (settings.wechat_pay_api_v3_key or "").strip().encode("utf-8")
        plain = AESGCM(key).decrypt(nonce, ciphertext, aad)
        _platform_certs[serial] = serialization.load_pem_public_key(plain)


def _verify_notify_signature(
    *,
    timestamp: str,
    nonce: str,
    body: str,
    signature_b64: str,
    serial: str,
) -> None:
    if serial not in _platform_certs:
        raise WeChatPayError("platform certificate not loaded")
    pub = _platform_certs[serial]
    message = f"{timestamp}\n{nonce}\n{body}\n".encode("utf-8")
    sig = base64.b64decode(signature_b64)
    pub.verify(sig, message, padding.PKCS1v15(), hashes.SHA256())


def _decrypt_resource(resource: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    api_v3_key = (settings.wechat_pay_api_v3_key or "").strip().encode("utf-8")
    if len(api_v3_key) != 32:
        raise WeChatPayError("WECHAT_PAY_API_V3_KEY must be 32 bytes")

    nonce = (resource.get("nonce") or "").encode("utf-8")
    aad = (resource.get("associated_data") or "").encode("utf-8")
    ciphertext = base64.b64decode(resource.get("ciphertext") or "")
    plain = AESGCM(api_v3_key).decrypt(nonce, ciphertext, aad)
    return json.loads(plain.decode("utf-8"))


async def parse_notify(body: bytes, headers: dict[str, str]) -> dict[str, Any]:
    """验签并解密支付结果通知，返回解密后的交易对象。"""
    text = body.decode("utf-8") if body else ""
    if not text:
        raise WeChatPayError("empty notify body")

    settings = get_settings()
    if settings.wechat_pay_use_mock:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise WeChatPayError("invalid mock notify") from exc

    sig = (headers.get("wechatpay-signature") or headers.get("Wechatpay-Signature") or "").strip()
    ts = (headers.get("wechatpay-timestamp") or headers.get("Wechatpay-Timestamp") or "").strip()
    nonce = (headers.get("wechatpay-nonce") or headers.get("Wechatpay-Nonce") or "").strip()
    serial = (headers.get("wechatpay-serial") or headers.get("Wechatpay-Serial") or "").strip()
    if not all([sig, ts, nonce, serial]):
        raise WeChatPayError("missing Wechatpay notify headers")

    if not _platform_certs:
        await _refresh_platform_certs()
    try:
        _verify_notify_signature(timestamp=ts, nonce=nonce, body=text, signature_b64=sig, serial=serial)
    except Exception:
        await _refresh_platform_certs()
        _verify_notify_signature(timestamp=ts, nonce=nonce, body=text, signature_b64=sig, serial=serial)

    envelope = json.loads(text)
    resource = envelope.get("resource") or {}
    return _decrypt_resource(resource)
