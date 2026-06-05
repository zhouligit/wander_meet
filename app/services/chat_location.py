"""聊天定位消息：JSON 存 text_content，msg_type=location。"""

from __future__ import annotations

import json

from fastapi import HTTPException

from app.services.chat_activity_rec import decode_activity_rec_payload
from app.schemas.activity import SendMessageRequest

_LOCATION_NAME_MAX = 120
_LOCATION_ADDRESS_MAX = 256


def _validate_lat_lng(lat: float, lng: float) -> None:
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise HTTPException(status_code=400, detail="Invalid lat or lng")
    if lat == 0 and lng == 0:
        raise HTTPException(status_code=400, detail="Invalid lat or lng")


def encode_location_payload(
    *,
    location_name: str,
    address: str | None,
    lat: float,
    lng: float,
) -> str:
    name = (location_name or "").strip()
    if not name or len(name) > _LOCATION_NAME_MAX:
        raise HTTPException(status_code=400, detail="locationName is required")
    addr = (address or "").strip()
    if len(addr) > _LOCATION_ADDRESS_MAX:
        raise HTTPException(status_code=400, detail="address too long")
    _validate_lat_lng(lat, lng)
    return json.dumps(
        {"name": name, "address": addr or None, "lat": lat, "lng": lng},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_location_payload(text_content: str | None) -> dict[str, str | float | None] | None:
    if not text_content:
        return None
    try:
        data = json.loads(text_content)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    name = str(data.get("name") or "").strip()
    lat = data.get("lat")
    lng = data.get("lng")
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return None
    if not name:
        return None
    return {
        "locationName": name,
        "address": (str(data.get("address") or "").strip() or None),
        "lat": lat_f,
        "lng": lng_f,
    }


def build_location_row_content(payload: SendMessageRequest) -> tuple[str, str]:
    if payload.lat is None or payload.lng is None:
        raise HTTPException(status_code=400, detail="lat and lng are required for location message")
    name = (payload.locationName or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="locationName is required for location message")
    text_content = encode_location_payload(
        location_name=name,
        address=payload.address,
        lat=float(payload.lat),
        lng=float(payload.lng),
    )
    return "location", text_content


def message_content_fields(
    msg_type: str, text_content: str | None, image_url: str | None
) -> dict[str, str | float | None]:
    """序列化为 API 响应字段（text / sticker / image / location）。"""
    if msg_type == "text":
        return {
            "text": text_content,
            "stickerId": None,
            "imageUrl": None,
            "locationName": None,
            "address": None,
            "lat": None,
            "lng": None,
            "recActivityId": None,
            "recActivityTitle": None,
        }
    if msg_type == "sticker":
        return {
            "text": None,
            "stickerId": text_content,
            "imageUrl": None,
            "locationName": None,
            "address": None,
            "lat": None,
            "lng": None,
            "recActivityId": None,
            "recActivityTitle": None,
        }
    if msg_type == "image":
        return {
            "text": None,
            "stickerId": None,
            "imageUrl": image_url,
            "locationName": None,
            "address": None,
            "lat": None,
            "lng": None,
            "recActivityId": None,
            "recActivityTitle": None,
        }
    if msg_type == "location":
        loc = decode_location_payload(text_content) or {}
        return {
            "text": None,
            "stickerId": None,
            "imageUrl": None,
            "locationName": loc.get("locationName"),
            "address": loc.get("address"),
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "recActivityId": None,
            "recActivityTitle": None,
        }
    if msg_type == "activity_rec":
        rec = decode_activity_rec_payload(text_content) or {}
        return {
            "text": None,
            "stickerId": None,
            "imageUrl": None,
            "locationName": None,
            "address": None,
            "lat": None,
            "lng": None,
            "recActivityId": rec.get("activityId"),
            "recActivityTitle": rec.get("activityTitle"),
        }
    return {
        "text": text_content,
        "stickerId": None,
        "imageUrl": image_url,
        "locationName": None,
        "address": None,
        "lat": None,
        "lng": None,
        "recActivityId": None,
        "recActivityTitle": None,
    }


def chat_last_message_preview(msg_type: str, text_content: str | None, image_url: str | None) -> str:
    if msg_type == "text":
        return (text_content or "").strip() or ""
    if msg_type == "image":
        return "[图片]"
    if msg_type == "sticker":
        return "[表情]"
    if msg_type == "location":
        loc = decode_location_payload(text_content)
        if loc and loc.get("locationName"):
            name = str(loc["locationName"])
            return f"[位置] {name[:24]}" if name else "[位置]"
        return "[位置]"
    if msg_type == "activity_rec":
        rec = decode_activity_rec_payload(text_content)
        if rec and rec.get("activityTitle"):
            return f"[活动] {rec['activityTitle'][:24]}"
        return "[活动推荐]"
    return "[消息]"
