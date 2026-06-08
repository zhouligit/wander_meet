"""群聊接龙：JSON 存 text_content，msg_type=chain_signup。"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import HTTPException

CHAIN_KIND = "chain_signup"
MAX_CHAIN_TITLE = 80
MAX_CHAIN_DESCRIPTION = 200
MAX_CHAIN_NOTE = 60
MAX_CHAIN_ENTRIES = 200

_CHAIN_TITLE_MIN = 2


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _entry_id_for_user(user_id: int) -> str:
    return f"e_{user_id}"


def _public_user_id(user_id: int) -> str:
    return f"u_{user_id}"


def _parse_public_user_id(user_id: str) -> int:
    s = (user_id or "").strip()
    if s.startswith("u_"):
        s = s[2:]
    if not s.isdigit():
        raise ValueError("invalid user id")
    return int(s)


def encode_chain_signup_payload(
    *,
    title: str,
    description: str = "",
    closed: bool = False,
    entries: list[dict] | None = None,
) -> str:
    title_s = (title or "").strip()
    if len(title_s) < _CHAIN_TITLE_MIN or len(title_s) > MAX_CHAIN_TITLE:
        raise HTTPException(status_code=400, detail="chainTitle length invalid")
    desc_s = (description or "").strip()
    if len(desc_s) > MAX_CHAIN_DESCRIPTION:
        raise HTTPException(status_code=400, detail="chainDescription too long")
    safe_entries = entries if isinstance(entries, list) else []
    if len(safe_entries) > MAX_CHAIN_ENTRIES:
        raise HTTPException(status_code=400, detail="chain entries limit reached")
    return json.dumps(
        {
            "kind": CHAIN_KIND,
            "title": title_s,
            "description": desc_s,
            "closed": bool(closed),
            "entries": safe_entries,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_chain_signup_payload(text_content: str | None) -> dict | None:
    if not text_content:
        return None
    try:
        data = json.loads(text_content)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("kind") != CHAIN_KIND:
        return None
    title = str(data.get("title") or "").strip()
    if not title:
        return None
    entries_raw = data.get("entries")
    entries: list[dict] = []
    if isinstance(entries_raw, list):
        for item in entries_raw:
            if not isinstance(item, dict):
                continue
            uid = str(item.get("userId") or "").strip()
            if not uid.startswith("u_"):
                continue
            entries.append(
                {
                    "entryId": str(item.get("entryId") or _entry_id_for_user(_parse_public_user_id(uid))),
                    "userId": uid,
                    "nickname": str(item.get("nickname") or "用户").strip() or "用户",
                    "note": str(item.get("note") or "").strip()[:MAX_CHAIN_NOTE],
                    "createdAt": str(item.get("createdAt") or ""),
                }
            )
    return {
        "title": title,
        "description": str(data.get("description") or "").strip(),
        "closed": bool(data.get("closed")),
        "entries": entries,
    }


def build_create_chain_content(
    *,
    title: str,
    description: str,
    user_id: int,
    nickname: str,
    note: str = "",
) -> str:
    note_s = (note or "").strip()[:MAX_CHAIN_NOTE]
    entries = [
        {
            "entryId": _entry_id_for_user(user_id),
            "userId": _public_user_id(user_id),
            "nickname": (nickname or "用户").strip() or "用户",
            "note": note_s,
            "createdAt": _now_iso(),
        }
    ]
    return encode_chain_signup_payload(title=title, description=description, entries=entries)


def add_or_update_entry(
    text_content: str | None,
    *,
    user_id: int,
    nickname: str,
    note: str,
) -> str:
    data = decode_chain_signup_payload(text_content)
    if not data:
        raise HTTPException(status_code=400, detail="Invalid chain signup message")
    if data["closed"]:
        raise HTTPException(status_code=400, detail="Chain signup is closed")
    note_s = (note or "").strip()[:MAX_CHAIN_NOTE]
    uid = _public_user_id(user_id)
    entries = list(data["entries"])
    existing = next((e for e in entries if e.get("userId") == uid), None)
    if existing:
        existing["nickname"] = (nickname or "用户").strip() or "用户"
        existing["note"] = note_s
    else:
        if len(entries) >= MAX_CHAIN_ENTRIES:
            raise HTTPException(status_code=400, detail="Chain signup is full")
        entries.append(
            {
                "entryId": _entry_id_for_user(user_id),
                "userId": uid,
                "nickname": (nickname or "用户").strip() or "用户",
                "note": note_s,
                "createdAt": _now_iso(),
            }
        )
    return encode_chain_signup_payload(
        title=data["title"],
        description=data["description"],
        closed=data["closed"],
        entries=entries,
    )


def remove_entry(text_content: str | None, *, user_id: int) -> str:
    data = decode_chain_signup_payload(text_content)
    if not data:
        raise HTTPException(status_code=400, detail="Invalid chain signup message")
    if data["closed"]:
        raise HTTPException(status_code=400, detail="Chain signup is closed")
    uid = _public_user_id(user_id)
    entries = [e for e in data["entries"] if e.get("userId") != uid]
    if len(entries) == len(data["entries"]):
        raise HTTPException(status_code=404, detail="Entry not found")
    return encode_chain_signup_payload(
        title=data["title"],
        description=data["description"],
        closed=data["closed"],
        entries=entries,
    )


def close_chain(text_content: str | None) -> str:
    data = decode_chain_signup_payload(text_content)
    if not data:
        raise HTTPException(status_code=400, detail="Invalid chain signup message")
    if data["closed"]:
        raise HTTPException(status_code=400, detail="Chain signup is already closed")
    return encode_chain_signup_payload(
        title=data["title"],
        description=data["description"],
        closed=True,
        entries=data["entries"],
    )
