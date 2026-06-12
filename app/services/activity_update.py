"""组织者修改活动：时间窗限制、人数校验、群聊变更通知。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.activity_message import ActivityMessage
from app.models.user import User
from app.services.activity_category import normalize_activity_category
from app.services.activity_query import HOME_ACTIVITY_WINDOW_DAYS, effective_activity_status, to_utc
from app.services.chat_unread import increment_chat_unread_for_message
from app.services.content_moderation import assert_text_fields_safe
from app.services.wechat_content_security import SCENE_FORUM

_TZ_BJ = ZoneInfo("Asia/Shanghai")

# 活动开始后仅允许修改说明
_IN_PROGRESS_ALLOWED = frozenset({"description"})


def activity_has_started(activity: Activity, now_utc: datetime | None = None) -> bool:
    now_utc = now_utc or datetime.now(UTC)
    return to_utc(activity.start_at) <= now_utc


def _format_time_bj(dt: datetime | None) -> str:
    if dt is None:
        return "未设置"
    local = to_utc(dt).astimezone(_TZ_BJ)
    return f"{local.month}/{local.day} {local.hour:02d}:{local.minute:02d}"


def _collect_change_lines(activity: Activity, updates: dict) -> list[str]:
    lines: list[str] = []
    if "title" in updates and updates["title"] != activity.title:
        lines.append(f"标题：{updates['title']}")
    if "description" in updates and updates["description"] != activity.description:
        lines.append("活动说明已更新")
    if "startAt" in updates:
        new_start = to_utc(updates["startAt"])
        if new_start != to_utc(activity.start_at):
            lines.append(f"开始时间：{_format_time_bj(new_start)}")
    if "endAt" in updates:
        new_end = to_utc(updates["endAt"]) if updates["endAt"] is not None else None
        old_end = to_utc(activity.end_at) if activity.end_at else None
        if new_end != old_end:
            lines.append(f"结束时间：{_format_time_bj(new_end)}")
    if "locationName" in updates and updates["locationName"] != activity.location_name:
        lines.append(f"地点：{updates['locationName']}")
    elif ("lat" in updates or "lng" in updates) and (
        updates.get("lat") != float(activity.lat) or updates.get("lng") != float(activity.lng)
    ):
        lines.append("见面坐标已更新")
    if "maxMembers" in updates and int(updates["maxMembers"]) != int(activity.max_members):
        lines.append(f"人数上限：{updates['maxMembers']} 人")
    return lines


async def apply_activity_update(
    db: AsyncSession,
    activity: Activity,
    organizer: User,
    updates: dict,
    *,
    now_utc: datetime | None = None,
) -> list[str]:
    """应用 PATCH 字段；返回需通知参与者的变更摘要行。"""
    now_utc = now_utc or datetime.now(UTC)
    status = effective_activity_status(activity, now_utc)
    if status in {"cancelled", "ended"}:
        raise HTTPException(status_code=400, detail="活动已结束或已取消，无法修改")
    if not updates:
        raise HTTPException(status_code=400, detail="没有可更新的字段")

    started = activity_has_started(activity, now_utc)
    if started:
        disallowed = set(updates.keys()) - _IN_PROGRESS_ALLOWED
        if disallowed:
            raise HTTPException(status_code=400, detail="活动进行中仅可修改活动说明")

    enrolled_count = int(
        await db.scalar(
            select(func.count(ActivityEnrollment.id)).where(
                ActivityEnrollment.activity_id == activity.id,
                ActivityEnrollment.status == "joined",
            )
        )
        or 0
    )

    if "maxMembers" in updates:
        cap = int(updates["maxMembers"])
        if cap < enrolled_count:
            raise HTTPException(
                status_code=400,
                detail=f"人数上限不能小于当前已报名人数（{enrolled_count} 人）",
            )

    if not started and "startAt" in updates:
        start_at_utc = to_utc(updates["startAt"])
        earliest = now_utc - timedelta(minutes=5)
        if start_at_utc < earliest:
            raise HTTPException(status_code=400, detail="开始时间不能早于当前时间")
        latest = now_utc + timedelta(days=HOME_ACTIVITY_WINDOW_DAYS)
        if start_at_utc > latest:
            raise HTTPException(
                status_code=400,
                detail="开始时间需在7天内：首页只展示近7天可参加的活动",
            )

    if "endAt" in updates and "startAt" in updates:
        if to_utc(updates["endAt"]) <= to_utc(updates["startAt"]):
            raise HTTPException(status_code=400, detail="结束时间需晚于开始时间")
    if "endAt" in updates and "startAt" not in updates and updates["endAt"] is not None:
        ref_start = activity.start_at
        if to_utc(updates["endAt"]) <= to_utc(ref_start):
            raise HTTPException(status_code=400, detail="结束时间需晚于开始时间")
    if "startAt" in updates and "endAt" not in updates and activity.end_at is not None:
        if to_utc(activity.end_at) <= to_utc(updates["startAt"]):
            raise HTTPException(status_code=400, detail="结束时间需晚于开始时间")

    mod_fields: dict[str, str] = {}
    if "title" in updates:
        mod_fields["title"] = updates["title"] or ""
    if "description" in updates:
        mod_fields["description"] = updates["description"] or ""
    if "locationName" in updates:
        mod_fields["locationName"] = updates["locationName"] or ""
    if "addressDetail" in updates and updates["addressDetail"]:
        mod_fields["addressDetail"] = updates["addressDetail"]
    if mod_fields:
        await assert_text_fields_safe(organizer, mod_fields, scene=SCENE_FORUM)

    notice_lines = _collect_change_lines(activity, updates)

    if "categoryId" in updates or "categoryLabel" in updates or "subCategoryId" in updates:
        new_cid = updates.get("categoryId", activity.category_id)
        new_sub = updates.get("subCategoryId", activity.sub_category_id)
        new_label = updates.get("categoryLabel", activity.category_label)
        cat_id, sub_id, cat_label = normalize_activity_category(
            new_cid, new_sub, new_label, allow_retired=True
        )
        if (
            cat_id != activity.category_id
            or sub_id != activity.sub_category_id
            or cat_label != activity.category_label
        ):
            notice_lines.append("活动分类已更新")
        activity.category_id = cat_id
        activity.sub_category_id = sub_id
        activity.category_label = cat_label
        updates.pop("categoryId", None)
        updates.pop("subCategoryId", None)
        updates.pop("categoryLabel", None)

    field_map = {
        "title": "title",
        "description": "description",
        "startAt": "start_at",
        "endAt": "end_at",
        "locationName": "location_name",
        "addressDetail": "address_detail",
        "lat": "lat",
        "lng": "lng",
        "maxMembers": "max_members",
        "feeType": "fee_type",
        "feeAmount": "fee_amount_cents",
    }
    for req_key, model_key in field_map.items():
        if req_key not in updates:
            continue
        val = updates[req_key]
        if req_key == "startAt":
            val = to_utc(val)
        elif req_key == "endAt":
            val = to_utc(val) if val is not None else None
        setattr(activity, model_key, val)

    if notice_lines:
        text = "【活动变更】发起人更新了活动信息\n" + "\n".join(notice_lines)
        await post_organizer_chat_notice(db, activity, organizer.id, text)

    return notice_lines


async def post_organizer_chat_notice(
    db: AsyncSession,
    activity: Activity,
    organizer_id: int,
    text: str,
) -> None:
    """向活动群聊发送发起人侧通知（变更/取消等）。"""
    body = (text or "").strip()
    if not body:
        return
    db.add(
        ActivityMessage(
            activity_id=activity.id,
            sender_id=organizer_id,
            msg_type="text",
            text_content=body,
        )
    )
    await db.flush()
    await increment_chat_unread_for_message(db, activity, organizer_id)
