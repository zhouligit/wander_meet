"""YunGouOS 微信支付：签名、Native 扫码、回调验签。"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from typing import Any
import httpx

from app.core.config import get_settings
from app.services.pay_common import build_attach, build_out_trade_no

logger = logging.getLogger(__name__)


class YunGouPayError(Exception):
    pass


def _md5_sign_upper(parts: list[tuple[str, str]], api_key: str) -> str:
    items = [f"{k}={v}" for k, v in sorted(parts, key=lambda x: x[0]) if v is not None and str(v) != ""]
    raw = "&".join(items) + f"&key={api_key}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def yungou_request_sign(params: dict[str, Any], api_key: str) -> str:
    """与 YunGouOS 官方 ``PaySignUtil.createSign`` 一致：仅对传入的非空参数签名。"""
    pairs = [(str(k), str(v)) for k, v in params.items() if k != "sign" and v is not None and str(v) != ""]
    return _md5_sign_upper(pairs, api_key)


def _native_pay_sign_params(
    *,
    mch_id: str,
    out_trade_no: str,
    total_fee: str,
    body: str,
) -> dict[str, str]:
    """Native 扫码：官方 SDK 仅对 4 个必填字段签名，其余字段在签名后追加。"""
    return {
        "mch_id": mch_id,
        "out_trade_no": out_trade_no,
        "total_fee": total_fee,
        "body": body,
    }


def yungou_notify_sign(form: dict[str, str], api_key: str) -> str:
    """回调验签字段：code, orderNo, payNo, outTradeNo, money, mchId。"""
    keys = ("code", "orderNo", "payNo", "outTradeNo", "money", "mchId")
    pairs = [(k, str(form.get(k, "") or "")) for k in keys]
    return _md5_sign_upper(pairs, api_key)


def verify_yungou_notify_sign(form: dict[str, str], api_key: str) -> bool:
    expected = (form.get("sign") or "").strip().upper()
    if not expected:
        return False
    return yungou_notify_sign(form, api_key) == expected


def _parse_yungou_response(data: Any) -> str:
    """从 YunGouOS 响应中取出支付链接 / 二维码 URL。"""
    if isinstance(data, str):
        s = data.strip()
        if s.startswith("weixin://") or s.startswith("http"):
            return s
        try:
            data = json.loads(s)
        except json.JSONDecodeError:
            return s
    if isinstance(data, dict):
        for key in ("codeUrl", "code_url", "payUrl", "pay_url", "url", "qrcode", "qrCode"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    raise YunGouPayError("YunGouOS response missing pay url")


async def native_pay(
    *,
    out_trade_no: str,
    total_fee: str,
    body: str,
    attach: str,
    notify_url: str,
) -> str:
    settings = get_settings()
    if settings.yungou_use_mock:
        return f"weixin://wxpay/bizpayurl?pr=mock_{out_trade_no[-12:]}"

    mch_id = (settings.yungou_mch_id or "").strip()
    api_key = (settings.yungou_api_key or "").strip()
    api_url = (settings.yungou_native_api or "").strip()
    if not mch_id or not api_key or not api_url:
        raise YunGouPayError("YunGouOS is not configured")

    sign_base = _native_pay_sign_params(
        mch_id=mch_id,
        out_trade_no=out_trade_no,
        total_fee=total_fee,
        body=body,
    )
    params: dict[str, Any] = {
        **sign_base,
        "type": "1",
        "attach": attach,
        "notify_url": notify_url,
    }
    params["sign"] = yungou_request_sign(sign_base, api_key)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(api_url, data=params)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        logger.exception("YunGouOS nativePay HTTP failed")
        raise YunGouPayError("YunGouOS request failed") from exc
    except json.JSONDecodeError as exc:
        raise YunGouPayError("YunGouOS invalid JSON") from exc

    code = payload.get("code")
    if code not in (0, "0", None) and str(code) != "0":
        msg = payload.get("msg") or payload.get("message") or str(payload)
        raise YunGouPayError(f"YunGouOS error: {msg}")

    data = payload.get("data")
    return _parse_yungou_response(data)


async def minapp_pay(
    *,
    out_trade_no: str,
    total_fee: str,
    body: str,
    attach: str,
    notify_url: str,
    wx_code: str,
) -> dict[str, str]:
    settings = get_settings()
    if settings.yungou_use_mock:
        return {
            "timeStamp": str(int(time.time())),
            "nonceStr": secrets.token_hex(8),
            "package": "prepay_id=mock",
            "signType": "RSA",
            "paySign": "mock_sign",
        }

    mch_id = (settings.yungou_mch_id or "").strip()
    api_key = (settings.yungou_api_key or "").strip()
    api_url = (settings.yungou_minapp_api or "").strip()
    if not mch_id or not api_key or not api_url:
        raise YunGouPayError("YunGouOS is not configured")

    sign_base = _native_pay_sign_params(
        mch_id=mch_id,
        out_trade_no=out_trade_no,
        total_fee=total_fee,
        body=body,
    )
    params: dict[str, Any] = {
        **sign_base,
        "attach": attach,
        "notify_url": notify_url,
        "code": wx_code,
    }
    params["sign"] = yungou_request_sign(sign_base, api_key)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(api_url, data=params)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        logger.exception("YunGouOS minAppPay HTTP failed")
        raise YunGouPayError("YunGouOS minipay request failed") from exc
    except json.JSONDecodeError as exc:
        raise YunGouPayError("YunGouOS invalid JSON") from exc

    code = payload.get("code")
    if code not in (0, "0", None) and str(code) != "0":
        msg = payload.get("msg") or payload.get("message") or str(payload)
        raise YunGouPayError(f"YunGouOS error: {msg}")

    data = payload.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            raise YunGouPayError("YunGouOS minipay data invalid") from None
    if not isinstance(data, dict):
        raise YunGouPayError("YunGouOS minipay data missing")

    out: dict[str, str] = {}
    for src, dst in (
        ("timeStamp", "timeStamp"),
        ("nonceStr", "nonceStr"),
        ("package", "package"),
        ("signType", "signType"),
        ("paySign", "paySign"),
    ):
        v = data.get(src) or data.get(src.lower())
        if v is not None:
            out[dst] = str(v)
    if not out.get("package"):
        raise YunGouPayError("YunGouOS minipay missing package")
    return out


