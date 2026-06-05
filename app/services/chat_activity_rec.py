"""群主推荐活动消息：JSON 存 text_content，msg_type=activity_rec。"""

from __future__ import annotations

import json

from fastapi import HTTPException


def encode_activity_rec_payload(*, activity_id: int, title: str) -> str:
    title_s = (title or "").strip()
    if not title_s:
        raise HTTPException(status_code=400, detail="activity title required")
    return json.dumps(
        {
            "kind": "activity_rec",
            "activityId": f"act_{activity_id}",
            "title": title_s[:80],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_activity_rec_payload(text_content: str | None) -> dict[str, str] | None:
    if not text_content:
        return None
    try:
        data = json.loads(text_content)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("kind") != "activity_rec":
        return None
    aid = str(data.get("activityId") or "").strip()
    title = str(data.get("title") or "").strip()
    if not aid.startswith("act_") or not title:
        return None
    return {"activityId": aid, "activityTitle": title}
