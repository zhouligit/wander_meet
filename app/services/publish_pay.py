"""发布活动付费：下单、查单、回调落库。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.pay_order import PayOrder
from app.models.user import User
from app.services.activity_query import to_utc, to_utc_optional
from app.services.pay_common import build_attach, build_out_trade_no, yuan_to_fen
from app.services.wechat_miniapp import WechatLoginError, code_to_session
from app.services.wechat_pay_v3 import (
    WeChatPayError,
    build_miniprogram_payment_params,
    jsapi_pay,
    native_pay,
)
from app.services.yungou_pay import YunGouPayError, minapp_pay, native_pay as yungou_native_pay

logger = logging.getLogger(__name__)


def parse_public_user_id(user_id: str) -> int:
    s = (user_id or "").strip()
    if s.startswith("u_"):
        s = s[2:]
    return int(s)


def public_user_id(uid: int) -> str:
    return f"u_{uid}"


def _assert_user_match(body_user_id: str, current_user: User) -> None:
    if public_user_id(current_user.id) != (body_user_id or "").strip():
        raise HTTPException(status_code=403, detail="user_id mismatch")


def _active_pay_provider() -> str:
    return (get_settings().pay_provider or "wechat").strip().lower()


def _use_wechat_mock() -> bool:
    settings = get_settings()
    return _active_pay_provider() == "wechat" and settings.wechat_pay_use_mock


def _use_yungou_mock() -> bool:
    settings = get_settings()
    return _active_pay_provider() == "yungou" and settings.yungou_use_mock


def _notify_url() -> str:
    settings = get_settings()
    if _active_pay_provider() == "yungou":
        return (settings.yungou_notify_url or "").strip()
    return (settings.wechat_pay_notify_url or "").strip()


async def _get_paid_order(
    db: AsyncSession, *, user_id: int, qr_id: str, product: str
) -> PayOrder | None:
    return await db.scalar(
        select(PayOrder).where(
            PayOrder.user_id == user_id,
            PayOrder.qr_id == qr_id,
            PayOrder.product == product,
            PayOrder.status == "paid",
        )
    )


async def _create_native_pay_url(
    *,
    out_trade_no: str,
    attach: str,
    notify_url: str,
) -> str:
    settings = get_settings()
    if _active_pay_provider() == "yungou":
        try:
            return await yungou_native_pay(
                out_trade_no=out_trade_no,
                total_fee=settings.pay_publish_fee_yuan,
                body=settings.pay_publish_body,
                attach=attach,
                notify_url=notify_url,
            )
        except YunGouPayError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        return await native_pay(
            out_trade_no=out_trade_no,
            total_fee_yuan=settings.pay_publish_fee_yuan,
            description=settings.pay_publish_body,
            attach=attach,
            notify_url=notify_url,
        )
    except WeChatPayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _create_jsapi_payment(
    *,
    out_trade_no: str,
    attach: str,
    notify_url: str,
    wx_code: str,
) -> dict[str, str]:
    settings = get_settings()
    if _active_pay_provider() == "yungou":
        try:
            return await minapp_pay(
                out_trade_no=out_trade_no,
                total_fee=settings.pay_publish_fee_yuan,
                body=settings.pay_publish_body,
                attach=attach,
                notify_url=notify_url,
                wx_code=wx_code,
            )
        except YunGouPayError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        session = await code_to_session(wx_code)
    except WechatLoginError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        prepay_id = await jsapi_pay(
            out_trade_no=out_trade_no,
            total_fee_yuan=settings.pay_publish_fee_yuan,
            description=settings.pay_publish_body,
            attach=attach,
            notify_url=notify_url,
            openid=session.openid,
        )
        return build_miniprogram_payment_params(prepay_id)
    except WeChatPayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def create_publish_qrcode_order(
    db: AsyncSession,
    *,
    current_user: User,
    qr_id: str,
    product: str,
) -> PayOrder:
    settings = get_settings()
    product = (product or settings.pay_publish_product).strip() or "publish"
    qr_id = (qr_id or "").strip()
    if not qr_id:
        raise HTTPException(status_code=400, detail="qr_id is required")

    if await _get_paid_order(db, user_id=current_user.id, qr_id=qr_id, product=product):
        raise HTTPException(status_code=409, detail="already paid")

    pending = await db.scalar(
        select(PayOrder)
        .where(
            PayOrder.user_id == current_user.id,
            PayOrder.qr_id == qr_id,
            PayOrder.product == product,
            PayOrder.status == "pending",
            PayOrder.expires_at > func.utc_timestamp(),
        )
        .order_by(PayOrder.id.desc())
        .limit(1)
    )
    if pending and pending.pay_code_url:
        return pending

    notify_url = _notify_url()
    if not notify_url and not (_use_wechat_mock() or _use_yungou_mock()):
        raise HTTPException(status_code=503, detail="pay notify URL not configured")

    out_trade_no = build_out_trade_no()
    attach = build_attach(public_user_id(current_user.id), qr_id, product)
    pay_url = await _create_native_pay_url(
        out_trade_no=out_trade_no, attach=attach, notify_url=notify_url
    )

    now = datetime.now(UTC)
    order = PayOrder(
        user_id=current_user.id,
        qr_id=qr_id,
        product=product,
        out_trade_no=out_trade_no,
        status="pending",
        channel="native",
        pay_provider=_active_pay_provider(),
        pay_code_url=pay_url,
        money=settings.pay_publish_fee_yuan,
        attach=attach,
        expires_at=now + timedelta(seconds=settings.pay_order_ttl_seconds),
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


async def create_publish_minipay_order(
    db: AsyncSession,
    *,
    current_user: User,
    qr_id: str,
    product: str,
    wx_code: str,
) -> tuple[PayOrder, dict[str, str]]:
    settings = get_settings()
    product = (product or settings.pay_publish_product).strip() or "publish"
    qr_id = (qr_id or "").strip()
    if not qr_id:
        raise HTTPException(status_code=400, detail="qr_id is required")

    if await _get_paid_order(db, user_id=current_user.id, qr_id=qr_id, product=product):
        raise HTTPException(status_code=409, detail="already paid")

    notify_url = _notify_url()
    if not notify_url and not (_use_wechat_mock() or _use_yungou_mock()):
        raise HTTPException(status_code=503, detail="pay notify URL not configured")

    out_trade_no = build_out_trade_no()
    attach = build_attach(public_user_id(current_user.id), qr_id, product)
    payment_params = await _create_jsapi_payment(
        out_trade_no=out_trade_no,
        attach=attach,
        notify_url=notify_url,
        wx_code=wx_code,
    )

    now = datetime.now(UTC)
    order = PayOrder(
        user_id=current_user.id,
        qr_id=qr_id,
        product=product,
        out_trade_no=out_trade_no,
        status="pending",
        channel="miniprogram",
        pay_provider=_active_pay_provider(),
        pay_code_url=None,
        money=settings.pay_publish_fee_yuan,
        attach=attach,
        expires_at=now + timedelta(seconds=settings.pay_order_ttl_seconds),
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order, payment_params


async def query_publish_pay_state(
    db: AsyncSession,
    *,
    user_id: int,
    qr_id: str,
    product: str,
) -> tuple[bool, str, datetime | None, str | None]:
    product = (product or get_settings().pay_publish_product).strip() or "publish"
    qr_id = (qr_id or "").strip()
    paid_order = await _get_paid_order(db, user_id=user_id, qr_id=qr_id, product=product)
    if paid_order:
        return True, "paid", to_utc_optional(paid_order.paid_at), paid_order.pay_provider

    now = datetime.now(UTC)
    row = await db.scalar(
        select(PayOrder)
        .where(
            PayOrder.user_id == user_id,
            PayOrder.qr_id == qr_id,
            PayOrder.product == product,
        )
        .order_by(PayOrder.id.desc())
        .limit(1)
    )
    if not row:
        return False, "not_found", None, None
    if row.status == "paid":
        return True, "paid", to_utc_optional(row.paid_at), row.pay_provider
    if row.status == "failed":
        return False, "failed", None, row.pay_provider
    expires_at = to_utc(row.expires_at)
    if expires_at <= now:
        return False, "expired", None, row.pay_provider
    return False, "pending", None, row.pay_provider


async def mark_order_paid_from_yungou_notify(
    db: AsyncSession,
    *,
    out_trade_no: str,
    platform_order_no: str | None,
    charge_id: str | None,
    money: str,
    success_code: str,
) -> PayOrder | None:
    order = await db.scalar(select(PayOrder).where(PayOrder.out_trade_no == out_trade_no))
    if not order:
        logger.warning("yungou notify unknown out_trade_no=%s", out_trade_no)
        return None

    settings = get_settings()
    if order.status == "paid":
        return order

    if money != settings.pay_publish_fee_yuan:
        order.status = "failed"
        await db.commit()
        logger.warning("yungou notify money mismatch out=%s money=%s", out_trade_no, money)
        return order

    if str(success_code) != str(settings.yungou_pay_success_code):
        order.status = "failed"
        await db.commit()
        return order

    order.status = "paid"
    order.platform_order_no = platform_order_no
    order.charge_id = charge_id
    order.paid_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(order)
    return order


async def mark_order_paid_mock(
    db: AsyncSession,
    *,
    user_id: int,
    qr_id: str,
    product: str,
) -> PayOrder | None:
    """开发 Mock：将 pending 订单标为 paid（仅 WECHAT_PAY_USE_MOCK / yungou mock）。"""
    settings = get_settings()
    if not (_use_wechat_mock() or _use_yungou_mock()):
        return None

    row = await db.scalar(
        select(PayOrder)
        .where(
            PayOrder.user_id == user_id,
            PayOrder.qr_id == qr_id,
            PayOrder.product == product,
            PayOrder.status == "pending",
        )
        .order_by(PayOrder.id.desc())
        .limit(1)
    )
    if not row:
        return None
    row.status = "paid"
    row.paid_at = datetime.now(UTC)
    row.platform_order_no = f"mock_{row.out_trade_no}"
    await db.commit()
    await db.refresh(row)
    return row


async def mark_order_paid_from_wechat_notify(
    db: AsyncSession,
    *,
    transaction: dict,
) -> PayOrder | None:
    out_trade_no = (transaction.get("out_trade_no") or "").strip()
    if not out_trade_no:
        logger.warning("wechat notify missing out_trade_no")
        return None

    order = await db.scalar(select(PayOrder).where(PayOrder.out_trade_no == out_trade_no))
    if not order:
        logger.warning("wechat notify unknown out_trade_no=%s", out_trade_no)
        return None

    if order.status == "paid":
        return order

    trade_state = (transaction.get("trade_state") or "").strip()
    if trade_state != "SUCCESS":
        if trade_state in ("CLOSED", "REVOKED", "PAYERROR"):
            order.status = "failed"
            await db.commit()
        return order

    settings = get_settings()
    amount = transaction.get("amount") or {}
    total_fen = amount.get("total")
    expected_fen = yuan_to_fen(settings.pay_publish_fee_yuan)
    if total_fen is not None and int(total_fen) != expected_fen:
        order.status = "failed"
        await db.commit()
        logger.warning(
            "wechat notify amount mismatch out=%s got=%s expect=%s",
            out_trade_no,
            total_fen,
            expected_fen,
        )
        return order

    attach = (transaction.get("attach") or "").strip()
    parts = attach.split(",")
    if len(parts) >= 3 and parts[2] != settings.pay_publish_product:
        logger.warning("wechat notify bad attach=%s", attach)
        return None

    order.status = "paid"
    order.platform_order_no = (transaction.get("transaction_id") or "").strip() or None
    order.charge_id = order.platform_order_no
    order.paid_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(order)
    return order
