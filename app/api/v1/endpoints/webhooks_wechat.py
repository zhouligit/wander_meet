"""微信小程序服务端回调（内容安全 mediaCheckAsync 等）。"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.activity_images import handle_wechat_media_check_callback
from app.services.wechat_mp_message import verify_wechat_mp_msg_signature

router = APIRouter(prefix="/webhooks/wechat", tags=["webhooks-wechat"])
logger = logging.getLogger(__name__)


def _require_valid_signature(signature: str, timestamp: str, nonce: str) -> None:
    token = (get_settings().wx_mp_message_token or "").strip()
    if not token:
        logger.error("WX_MP_MESSAGE_TOKEN not configured")
        raise HTTPException(status_code=503, detail="message token not configured")
    if not verify_wechat_mp_msg_signature(token, signature, timestamp, nonce):
        raise HTTPException(status_code=403, detail="invalid signature")


def _extract_media_check_payload(body: dict) -> tuple[str, str, int | None]:
    trace_id = str(body.get("trace_id") or body.get("traceId") or "").strip()
    detail = body.get("detail")
    suggest = ""
    label: int | None = None
    if isinstance(detail, list) and detail:
        first = detail[0] if isinstance(detail[0], dict) else {}
        suggest = str(first.get("suggest") or "").strip()
        raw_label = first.get("label")
        if raw_label is not None:
            try:
                label = int(raw_label)
            except (TypeError, ValueError):
                label = None
    elif isinstance(body.get("result"), dict):
        suggest = str(body["result"].get("suggest") or "").strip()
        raw_label = body["result"].get("label")
        if raw_label is not None:
            try:
                label = int(raw_label)
            except (TypeError, ValueError):
                label = None
    if not suggest and "isrisky" in body:
        risky = int(body.get("isrisky") or 0)
        suggest = "risky" if risky else "pass"
    if not suggest:
        suggest = str(body.get("suggest") or "pass").strip()
    return trace_id, suggest, label


async def _parse_json_body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    return data


@router.get("/media-check")
async def wechat_media_check_verify(
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
) -> PlainTextResponse:
    """微信消息推送 URL 验证：验签通过后原样返回 ``echostr``。"""
    _require_valid_signature(signature, timestamp, nonce)
    return PlainTextResponse(content=echostr)


@router.post("/media-check")
async def wechat_media_check_callback(
    request: Request,
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    db: AsyncSession = Depends(get_db_session),
) -> PlainTextResponse:
    """微信 ``wxa_media_check`` 异步审核结果（消息推送 JSON 明文）。"""
    _require_valid_signature(signature, timestamp, nonce)
    body = await _parse_json_body(request)

    event = str(body.get("Event") or "").strip()
    if event and event != "wxa_media_check":
        logger.info("wechat media-check ignored event=%s", event)
        return PlainTextResponse(content="success")

    trace_id, suggest, label = _extract_media_check_payload(body)
    if not trace_id:
        logger.warning("wechat media-check callback missing trace_id body=%s", body)
        return PlainTextResponse(content="success")

    matched = await handle_wechat_media_check_callback(
        db, trace_id=trace_id, suggest=suggest, label=label
    )
    if matched:
        await db.commit()
        logger.info("wechat media-check applied trace_id=%s suggest=%s", trace_id, suggest)
    return PlainTextResponse(content="success")
