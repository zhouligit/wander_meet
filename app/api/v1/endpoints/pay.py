import logging
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.pay import (
    PayMinipayData,
    PayProductRequest,
    PayPublishMinipayRequest,
    PayPublishQrcodeData,
    PayPublishQrcodeRequest,
    PayStateData,
)
from app.services.publish_pay import (
    _assert_user_match,
    create_publish_minipay_order,
    create_publish_qrcode_order,
    mark_order_paid_from_wechat_notify,
    mark_order_paid_from_yungou_notify,
    mark_order_paid_mock,
    query_publish_pay_state,
)
from app.services.wechat_pay_v3 import WeChatPayError, parse_notify
from app.services.yungou_pay import verify_yungou_notify_sign

router = APIRouter(prefix="/pay", tags=["pay"])
logger = logging.getLogger(__name__)


async def _parse_yungou_notify_form(request: Request) -> dict[str, str]:
    """YunGouOS 回调为 ``application/x-www-form-urlencoded``（遗留通道）。"""
    body = await request.body()
    if not body:
        return {}
    text = body.decode("utf-8", errors="replace").lstrip("\ufeff")
    return dict(parse_qsl(text, keep_blank_values=True))


@router.post("/publish/qrcode")
async def pay_publish_qrcode(
    payload: PayPublishQrcodeRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PayPublishQrcodeData]:
    _assert_user_match(payload.user_id, current_user)
    order = await create_publish_qrcode_order(
        db,
        current_user=current_user,
        qr_id=payload.qr_id,
        product=payload.product,
    )
    settings = get_settings()
    return APIResponse(
        data=PayPublishQrcodeData(
            qrId=order.qr_id,
            outTradeNo=order.out_trade_no,
            payCodeUrl=order.pay_code_url or "",
            feeYuan=settings.pay_publish_fee_yuan,
        )
    )


@router.post("/publish/minipay")
async def pay_publish_minipay(
    payload: PayPublishMinipayRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PayMinipayData]:
    _assert_user_match(payload.user_id, current_user)
    order, payment_params = await create_publish_minipay_order(
        db,
        current_user=current_user,
        qr_id=payload.qr_id,
        product=payload.product,
        wx_code=payload.code,
    )
    settings = get_settings()
    mock_skip = settings.wechat_pay_use_mock and (settings.pay_provider or "").strip().lower() == "wechat"
    return APIResponse(
        data=PayMinipayData(
            qrId=order.qr_id,
            outTradeNo=order.out_trade_no,
            paymentParams=None if mock_skip else payment_params,
            mockSkip=mock_skip,
            feeYuan=settings.pay_publish_fee_yuan,
        )
    )


@router.post("/publish/sync")
async def pay_publish_sync(
    payload: PayProductRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PayStateData]:
    """支付成功后主动查微信单并落库（不依赖异步 notify）。"""
    _assert_user_match(payload.user_id, current_user)
    paid, state, paid_at, pay_channel = await query_publish_pay_state(
        db,
        user_id=current_user.id,
        qr_id=payload.qr_id,
        product=payload.product,
    )
    logger.info(
        "pay_publish_sync user_id=%s qr_id=%s paid=%s state=%s",
        current_user.id,
        payload.qr_id,
        paid,
        state,
    )
    return APIResponse(
        data=PayStateData.from_order(
            paid=paid, state=state, paid_at=paid_at, pay_channel=pay_channel
        )
    )


@router.post("/state")
async def pay_state(
    payload: PayProductRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PayStateData]:
    _assert_user_match(payload.user_id, current_user)
    paid, state, paid_at, pay_channel = await query_publish_pay_state(
        db,
        user_id=current_user.id,
        qr_id=payload.qr_id,
        product=payload.product,
    )
    logger.info(
        "pay_state user_id=%s qr_id=%s paid=%s state=%s channel=%s",
        current_user.id,
        payload.qr_id,
        paid,
        state,
        pay_channel,
    )
    return APIResponse(
        data=PayStateData.from_order(
            paid=paid, state=state, paid_at=paid_at, pay_channel=pay_channel
        )
    )


@router.post("/mock/confirm")
async def pay_mock_confirm(
    payload: PayProductRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PayStateData]:
    """开发 Mock：模拟支付成功（须 WECHAT_PAY_USE_MOCK 或 YUNGOU_USE_MOCK）。"""
    _assert_user_match(payload.user_id, current_user)
    settings = get_settings()
    if not (
        (settings.wechat_pay_use_mock and (settings.pay_provider or "").lower() == "wechat")
        or (settings.yungou_use_mock and (settings.pay_provider or "").lower() == "yungou")
    ):
        raise HTTPException(status_code=403, detail="mock confirm disabled")

    order = await mark_order_paid_mock(
        db,
        user_id=current_user.id,
        qr_id=payload.qr_id,
        product=payload.product,
    )
    if order is None:
        return APIResponse(code=40001, message="no pending order", data=None)
    return APIResponse(
        data=PayStateData.from_order(
            paid=True,
            state="paid",
            paid_at=order.paid_at,
            pay_channel=order.pay_provider,
        )
    )


@router.post("/wechat/notify")
async def pay_wechat_notify(request: Request, db: AsyncSession = Depends(get_db_session)) -> JSONResponse:
    """微信支付 APIv3 异步通知（无 Bearer）。"""
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        transaction = await parse_notify(body, headers)
    except WeChatPayError as exc:
        logger.warning("wechat notify parse failed: %s", exc)
        return JSONResponse({"code": "FAIL", "message": str(exc)}, status_code=400)

    if get_settings().wechat_pay_use_mock:
        out_trade_no = (transaction.get("out_trade_no") or "").strip()
        if out_trade_no:
            await mark_order_paid_from_wechat_notify(
                db,
                transaction={
                    "out_trade_no": out_trade_no,
                    "trade_state": "SUCCESS",
                    "transaction_id": transaction.get("transaction_id"),
                    "amount": {"total": transaction.get("amount", {}).get("total")},
                    "attach": transaction.get("attach"),
                },
            )
        return JSONResponse({"code": "SUCCESS", "message": "成功"})

    order = await mark_order_paid_from_wechat_notify(db, transaction=transaction)
    if order is None and (transaction.get("trade_state") or "") == "SUCCESS":
        return JSONResponse({"code": "FAIL", "message": "order not found"}, status_code=404)
    return JSONResponse({"code": "SUCCESS", "message": "成功"})


@router.post("/yungou/notify")
async def pay_yungou_notify(request: Request, db: AsyncSession = Depends(get_db_session)) -> PlainTextResponse:
    """YunGouOS 支付回调（遗留通道，生产停用）。"""
    form_str = await _parse_yungou_notify_form(request)
    settings = get_settings()
    api_key = (settings.yungou_api_key or "").strip()
    if not api_key:
        logger.error("yungou notify: missing API key")
        return PlainTextResponse("FAIL", status_code=500)

    if not verify_yungou_notify_sign(form_str, api_key):
        logger.warning("yungou notify bad sign out=%s", form_str.get("outTradeNo"))
        return PlainTextResponse("FAIL", status_code=400)

    attach = (form_str.get("attach") or "").strip()
    parts = attach.split(",")
    if len(parts) < 3 or parts[2] != settings.pay_publish_product:
        logger.warning("yungou notify bad attach=%s", attach)
        return PlainTextResponse("FAIL", status_code=400)

    out_trade_no = (form_str.get("outTradeNo") or "").strip()
    if not out_trade_no:
        return PlainTextResponse("FAIL", status_code=400)

    order = await mark_order_paid_from_yungou_notify(
        db,
        out_trade_no=out_trade_no,
        platform_order_no=(form_str.get("orderNo") or "").strip() or None,
        charge_id=(form_str.get("payNo") or "").strip() or None,
        money=(form_str.get("money") or "").strip(),
        success_code=(form_str.get("code") or "").strip(),
    )
    if order is None:
        return PlainTextResponse("FAIL", status_code=404)
    return PlainTextResponse("SUCCESS")
