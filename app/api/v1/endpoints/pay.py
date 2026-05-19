import logging
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
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
    mark_order_paid_from_notify,
    query_publish_pay_state,
)
from app.services.yungou_pay import verify_yungou_notify_sign

router = APIRouter(prefix="/pay", tags=["pay"])
logger = logging.getLogger(__name__)


async def _parse_yungou_notify_form(request: Request) -> dict[str, str]:
    """YunGouOS 回调为 ``application/x-www-form-urlencoded``（见 doc/pay_api.md）。"""
    body = await request.body()
    if not body:
        return {}
    ct = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if "multipart/form-data" in ct:
        form = await request.form()
        return {k: str(v) for k, v in form.items()}
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
    return APIResponse(
        data=PayPublishQrcodeData(
            qrId=order.qr_id,
            outTradeNo=order.out_trade_no,
            payCodeUrl=order.pay_code_url or "",
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
    return APIResponse(
        data=PayMinipayData(
            qrId=order.qr_id,
            outTradeNo=order.out_trade_no,
            paymentParams=payment_params,
        )
    )


@router.post("/state")
async def pay_state(
    payload: PayProductRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PayStateData]:
    _assert_user_match(payload.user_id, current_user)
    paid, state, paid_at = await query_publish_pay_state(
        db,
        user_id=current_user.id,
        qr_id=payload.qr_id,
        product=payload.product,
    )
    return APIResponse(data=PayStateData.from_order(paid=paid, state=state, paid_at=paid_at))


@router.post("/yungou/notify")
async def pay_yungou_notify(request: Request, db: AsyncSession = Depends(get_db_session)) -> PlainTextResponse:
    """YunGouOS 支付回调；无 Bearer。验签通过后订单标为 paid。"""
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

    order = await mark_order_paid_from_notify(
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
