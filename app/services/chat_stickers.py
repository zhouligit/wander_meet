"""官方聊天贴纸（固定 catalog，msg_type=sticker 时 stickerId 存 text_content）。"""

from __future__ import annotations

from fastapi import HTTPException

# 与小程序 src/constants/chatStickers.js 的 id 保持一致
OFFICIAL_STICKER_IDS: frozenset[str] = frozenset(
    {
        "travel_wave",
        "travel_hi",
        "travel_map",
        "travel_hike",
        "travel_coffee",
        "travel_sun",
        "travel_camera",
        "travel_tent",
        "react_ok",
        "react_thanks",
        "react_love",
        "react_laugh",
        "react_cool",
        "react_clap",
        "react_party",
        "react_sad",
    }
)


def validate_sticker_id(sticker_id: str) -> str:
    sid = (sticker_id or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="stickerId is required for sticker message")
    if sid not in OFFICIAL_STICKER_IDS:
        raise HTTPException(status_code=400, detail="Unknown stickerId")
    return sid


def message_content_fields(
    msg_type: str, text_content: str | None, image_url: str | None
) -> dict[str, str | float | None]:
    """兼容旧引用，委托 chat_location.message_content_fields。"""
    from app.services.chat_location import message_content_fields as _fields

    return _fields(msg_type, text_content, image_url)
