"""活动说明页：全站模板章节 + 自由编辑；概况/费用与活动主字段引用同步。"""

from __future__ import annotations

from fastapi import HTTPException

from app.models.activity import Activity

# 可持久化章节（camelCase，与前端/API 一致）
GUIDE_SECTION_KEYS = (
    "overviewNote",
    "itinerary",
    "equipment",
    "enrollmentRequirements",
    "feeNote",
    "registration",
    "risk",
    "environment",
)

GUIDE_SECTION_LABELS: dict[str, str] = {
    "overviewNote": "活动概况补充",
    "itinerary": "行程安排",
    "equipment": "装备要求",
    "enrollmentRequirements": "报名条件",
    "feeNote": "费用说明补充",
    "registration": "报名方式",
    "risk": "风险提示",
    "environment": "环保要求",
}

_GUIDE_SECTION_MAX_LEN = 8000


def normalize_guide_sections(raw: dict | None) -> dict[str, str]:
    if not raw or not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key in GUIDE_SECTION_KEYS:
        if key not in raw:
            continue
        val = raw.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if not text:
            continue
        if len(text) > _GUIDE_SECTION_MAX_LEN:
            raise HTTPException(
                status_code=400,
                detail=f"{GUIDE_SECTION_LABELS.get(key, key)} 过长（最多 {_GUIDE_SECTION_MAX_LEN} 字）",
            )
        out[key] = text
    return out


def guide_sections_for_api(activity: Activity) -> dict[str, str] | None:
    raw = activity.guide_sections
    if not raw or not isinstance(raw, dict):
        return None
    normalized = normalize_guide_sections(raw)
    return normalized or None


def guide_has_content(sections: dict[str, str] | None) -> bool:
    if not sections:
        return False
    return any((v or "").strip() for v in sections.values())


def guide_template_for_meta() -> list[dict[str, str]]:
    ordinals = "一二三四五六七八"
    items: list[dict[str, str]] = []
    display_keys = [k for k in GUIDE_SECTION_KEYS if k != "overviewNote"]
    for i, key in enumerate(display_keys):
        ord_label = ordinals[i] if i < len(ordinals) else str(i + 1)
        items.append(
            {
                "key": key,
                "label": GUIDE_SECTION_LABELS[key],
                "ordinal": ord_label,
                "placeholder": GUIDE_SECTION_PLACEHOLDERS.get(key, ""),
            }
        )
    return items


GUIDE_SECTION_PLACEHOLDERS: dict[str, str] = {
    "itinerary": "按时间列出集合、出发、登顶、下撤等节点；可注明「实际时间灵活调整」。",
    "equipment": "必备 / 建议 / 禁止携带的装备清单。",
    "enrollmentRequirements": "年龄、经验、健康要求、需签署协议等。",
    "feeNote": "在上方引用费用基础上，补充包含/不含项目、退改政策等。",
    "registration": "进群、联系微信、缴费方式等。",
    "risk": "天气、路况、人身风险及免责提示。",
    "environment": "无痕山野、垃圾带走等要求。",
    "overviewNote": "可补充难度等级、集合细节等（名称/时间/地点/人数已自动引用）。",
}


def fee_label_for_activity(activity: Activity) -> str:
    if not activity.fee_type or activity.fee_type == "free":
        return "免费"
    if activity.fee_amount_cents:
        yuan = activity.fee_amount_cents / 100
        if yuan == int(yuan):
            return f"{int(yuan)} 元"
        return f"{yuan:.2f} 元"
    if activity.fee_type == "aa":
        return "AA 制"
    return activity.fee_type


def build_guide_overview(activity: Activity, enrolled_count: int) -> dict:
    return {
        "title": activity.title,
        "startAt": activity.start_at,
        "endAt": activity.end_at,
        "locationName": activity.location_name,
        "addressDetail": activity.address_detail,
        "maxMembers": activity.max_members,
        "enrolledCount": enrolled_count,
        "feeType": activity.fee_type or "free",
        "feeAmount": activity.fee_amount_cents,
        "feeLabel": fee_label_for_activity(activity),
    }


async def apply_activity_guide_sections(
    activity: Activity,
    organizer,
    raw_sections: dict | None,
) -> None:
    """``raw_sections`` 为 ``None`` 跳过；``{}`` 清空。"""
    if raw_sections is None:
        return
    if not raw_sections:
        activity.guide_sections = None
        return
    from app.services.content_moderation import assert_text_fields_safe
    from app.services.wechat_content_security import SCENE_FORUM

    sections = normalize_guide_sections(raw_sections)
    if sections:
        await assert_text_fields_safe(
            organizer,
            {GUIDE_SECTION_LABELS[k]: v for k, v in sections.items()},
            scene=SCENE_FORUM,
        )
    activity.guide_sections = sections or None


def guide_fields_for_api(activity: Activity, enrolled_count: int) -> dict:
    sections = guide_sections_for_api(activity)
    return {
        "guideSections": sections,
        "guideFilled": guide_has_content(sections),
        "guideOverview": build_guide_overview(activity, enrolled_count),
    }
