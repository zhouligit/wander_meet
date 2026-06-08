"""群聊 @ 成员：text_content JSON 扩展（兼容纯文本）。"""

from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_enrollment import ActivityEnrollment
from app.models.user import User
from app.schemas.activity import ChatMentionItem

MENTIONS_KIND = "text_mentions"
MAX_MENTIONS_PER_MESSAGE = 5


def _public_user_id(user_id: int) -> str:
    return f"u_{user_id}"


def parse_public_user_id(user_id: str) -> int:
    s = (user_id or "").strip()
    if s.startswith("u_"):
        s = s[2:]
    if not s.isdigit():
        raise ValueError("invalid user id")
    return int(s)


def encode_text_mentions_payload(*, text: str, mentions: list[dict]) -> str:
    body = (text or "").strip()
    if not mentions:
        return body
    safe: list[dict] = []
    for m in mentions[:MAX_MENTIONS_PER_MESSAGE]:
        uid = str(m.get("userId") or "").strip()
        nick = str(m.get("nickname") or "").strip()
        if not uid.startswith("u_") or not nick:
            continue
        item: dict = {"userId": uid, "nickname": nick}
        if m.get("start") is not None:
            item["start"] = int(m["start"])
        if m.get("end") is not None:
            item["end"] = int(m["end"])
        safe.append(item)
    if not safe:
        return body
    return json.dumps(
        {"kind": MENTIONS_KIND, "text": body, "mentions": safe},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_text_payload(text_content: str | None) -> tuple[str | None, list[dict]]:
    if not text_content:
        return None, []
    raw = text_content.strip()
    if not raw:
        return None, []
    if not raw.startswith("{"):
        return text_content, []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return text_content, []
    if not isinstance(data, dict) or data.get("kind") != MENTIONS_KIND:
        return text_content, []
    text = str(data.get("text") or "")
    mentions_raw = data.get("mentions")
    mentions: list[dict] = []
    if isinstance(mentions_raw, list):
        for item in mentions_raw:
            if not isinstance(item, dict):
                continue
            uid = str(item.get("userId") or "").strip()
            nick = str(item.get("nickname") or "").strip()
            if not uid.startswith("u_") or not nick:
                continue
            row = {"userId": uid, "nickname": nick}
            if item.get("start") is not None:
                row["start"] = int(item["start"])
            if item.get("end") is not None:
                row["end"] = int(item["end"])
            mentions.append(row)
    return text, mentions


def normalize_client_mentions(
    text: str, mentions: list[ChatMentionItem] | None
) -> list[dict]:
    if not mentions:
        return []
    body = (text or "").strip()
    if not body:
        return []
    seen: set[str] = set()
    out: list[dict] = []
    for m in mentions[:MAX_MENTIONS_PER_MESSAGE]:
        uid = (m.userId or "").strip()
        nick = (m.nickname or "").strip()
        if not uid.startswith("u_") or not nick or uid in seen:
            continue
        needle = f"@{nick}"
        if needle not in body:
            continue
        seen.add(uid)
        start = m.start if m.start is not None else body.find(needle)
        end = m.end if m.end is not None else start + len(needle)
        out.append({"userId": uid, "nickname": nick, "start": start, "end": end})
    return out


async def assert_mentions_are_members(
    db: AsyncSession, activity_id: int, mention_user_ids: list[int]
) -> None:
    if not mention_user_ids:
        return
    unique = list(dict.fromkeys(mention_user_ids))
    rows = await db.execute(
        select(ActivityEnrollment.user_id).where(
            ActivityEnrollment.activity_id == activity_id,
            ActivityEnrollment.status == "joined",
            ActivityEnrollment.user_id.in_(unique),
        )
    )
    found = {int(r[0]) for r in rows.all()}
    missing = [uid for uid in unique if uid not in found]
    if missing:
        raise HTTPException(status_code=400, detail="Invalid mention target")


async def build_validated_text_content(
    db: AsyncSession,
    *,
    activity_id: int,
    text: str,
    mentions: list[ChatMentionItem] | None,
    strict: bool = False,
) -> str:
    body = (text or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="text is required for text message")
    from app.services.local_text_content_filter import local_text_blocked_reason
    from app.services.wechat_content_security import CONTENT_VIOLATION_MESSAGE

    blocked = local_text_blocked_reason(body, strict=strict)
    if blocked:
        raise HTTPException(status_code=400, detail=CONTENT_VIOLATION_MESSAGE)
    normalized = normalize_client_mentions(body, mentions)
    if len(normalized) > MAX_MENTIONS_PER_MESSAGE:
        raise HTTPException(status_code=400, detail="Too many mentions")
    user_ids = [parse_public_user_id(m["userId"]) for m in normalized]
    await assert_mentions_are_members(db, activity_id, user_ids)
    return encode_text_mentions_payload(text=body, mentions=normalized)
