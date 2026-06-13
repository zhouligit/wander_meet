"""微信小程序服务端回调（内容安全 mediaCheckAsync 等）。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.activity_images import handle_wechat_media_check_callback

router = APIRouter(prefix="/webhooks/wechat", tags=["webhooks-wechat"])
logger = logging.getLogger(__name__)


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
    if not suggest:
        suggest = str(body.get("suggest") or "pass").strip()
    return trace_id, suggest, label


@router.post("/media-check")
async def wechat_media_check_callback(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """微信 ``wxa_media_check`` 异步审核结果。"""
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid payload")

    trace_id, suggest, label = _extract_media_check_payload(body)
    if not trace_id:
        logger.warning("wechat media-check callback missing trace_id body=%s", body)
        return {"errcode": "0", "errmsg": "ok"}

    matched = await handle_wechat_media_check_callback(
        db, trace_id=trace_id, suggest=suggest, label=label
    )
    if matched:
        await db.commit()
    return {"errcode": "0", "errmsg": "ok"}
