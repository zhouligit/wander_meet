"""发布活动付费：下单、查单、回调落库。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.pay_order import PayOrder
from app.models.user import User
from app.services.activity_query import to_utc, to_utc_optional
from app.services.yungou_pay import (
    YunGouPayError,
    build_attach,
    build_out_trade_no,
    minapp_pay,
    native_pay,
)

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

    now = datetime.now(UTC)
    pending = await db.scalar(
        select(PayOrder)
        .where(
            PayOrder.user_id == current_user.id,
            PayOrder.qr_id == qr_id,
            PayOrder.product == product,
            PayOrder.status == "pending",
            PayOrder.expires_at > now,
        )
        .order_by(PayOrder.id.desc())
        .limit(1)
    )
    if pending and pending.pay_code_url:
        return pending

    out_trade_no = build_out_trade_no()
    attach = build_attach(public_user_id(current_user.id), qr_id, product)
    notify_url = (settings.yungou_notify_url or "").strip()
    if not notify_url and not settings.yungou_use_mock:
        raise HTTPException(status_code=503, detail="YUNGOU_NOTIFY_URL not configured")

    try:
        pay_url = await native_pay(
            out_trade_no=out_trade_no,
            total_fee=settings.pay_publish_fee_yuan,
            body=settings.pay_publish_body,
            attach=attach,
            notify_url=notify_url,
        )
    except YunGouPayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    order = PayOrder(
        user_id=current_user.id,
        qr_id=qr_id,
        product=product,
        out_trade_no=out_trade_no,
        status="pending",
        channel="native",
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

    out_trade_no = build_out_trade_no()
    attach = build_attach(public_user_id(current_user.id), qr_id, product)
    notify_url = (settings.yungou_notify_url or "").strip()
    if not notify_url and not settings.yungou_use_mock:
        raise HTTPException(status_code=503, detail="YUNGOU_NOTIFY_URL not configured")

    try:
        payment_params = await minapp_pay(
            out_trade_no=out_trade_no,
            total_fee=settings.pay_publish_fee_yuan,
            body=settings.pay_publish_body,
            attach=attach,
            notify_url=notify_url,
            wx_code=wx_code,
        )
    except YunGouPayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    now = datetime.now(UTC)
    order = PayOrder(
        user_id=current_user.id,
        qr_id=qr_id,
        product=product,
        out_trade_no=out_trade_no,
        status="pending",
        channel="miniprogram",
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
) -> tuple[bool, str, datetime | None]:
    product = (product or get_settings().pay_publish_product).strip() or "publish"
    qr_id = (qr_id or "").strip()
    paid_order = await _get_paid_order(db, user_id=user_id, qr_id=qr_id, product=product)
    if paid_order:
        return True, "paid", to_utc_optional(paid_order.paid_at)

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
        return False, "not_found", None
    if row.status == "paid":
        return True, "paid", to_utc_optional(row.paid_at)
    if row.status == "failed":
        return False, "failed", None
    expires_at = to_utc(row.expires_at)
    if expires_at <= now:
        return False, "expired", None
    return False, "pending", None


async def mark_order_paid_from_notify(
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
