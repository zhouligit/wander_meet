"""活动封面图：BOS 白名单、微信 mediaCheckAsync 审核、公众可见性。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.activity import Activity
from app.models.activity_media_audit import ActivityMediaAudit
from app.models.user import User
from app.services.activity_query import to_utc_optional
from app.services.bos_storage import validate_stored_activity_image_url, resolve_bos_read_url
from app.services.wechat_content_security import SCENE_FORUM, media_check_async

logger = logging.getLogger(__name__)

MAX_ACTIVITY_IMAGES = 9
PENDING_TIMEOUT_MINUTES = 30

IMAGES_AUDIT_NONE = "none"
IMAGES_AUDIT_PENDING = "pending"
IMAGES_AUDIT_PASS = "pass"
IMAGES_AUDIT_REJECT = "reject"

_RISKY_SUGGESTS = frozenset({"risky", "review"})


def validate_activity_image_urls(user_id: int, urls: list[str]) -> list[str]:
    if len(urls) > MAX_ACTIVITY_IMAGES:
        raise HTTPException(status_code=400, detail=f"最多 {MAX_ACTIVITY_IMAGES} 张活动图片")
    seen: set[str] = set()
    out: list[str] = []
    for raw in urls:
        u = validate_stored_activity_image_url(raw, user_id)
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def public_cover_image_url(activity: Activity) -> str | None:
    if activity.images_audit_status == IMAGES_AUDIT_PASS and activity.cover_image_url:
        return resolve_bos_read_url(activity.cover_image_url)
    return None


def _presigned_image_list(urls: list[str] | None) -> list[str] | None:
    if not urls:
        return None
    return [resolve_bos_read_url(u) or u for u in urls]


def activity_image_fields_for_api(
    activity: Activity, viewer_user_id: int | None
) -> dict[str, str | list[str] | None]:
    """公众/非组织者：审核通过前不返回图片 URL。"""
    is_organizer = viewer_user_id is not None and viewer_user_id == activity.organizer_id
    status = activity.images_audit_status or IMAGES_AUDIT_NONE
    if is_organizer:
        return {
            "coverImageUrl": resolve_bos_read_url(activity.cover_image_url),
            "images": _presigned_image_list(list(activity.images or []) if activity.images else None),
            "imagesAuditStatus": status,
        }
    if status == IMAGES_AUDIT_PASS:
        return {
            "coverImageUrl": resolve_bos_read_url(activity.cover_image_url),
            "images": _presigned_image_list(list(activity.images or []) if activity.images else None),
            "imagesAuditStatus": status,
        }
    return {
        "coverImageUrl": None,
        "images": None,
        "imagesAuditStatus": status if status != IMAGES_AUDIT_NONE else IMAGES_AUDIT_NONE,
    }


def _should_auto_pass_media_check(organizer: User) -> bool:
    settings = get_settings()
    if settings.wx_mp_use_mock or not settings.wx_content_sec_enabled:
        return True
    if not (organizer.mp_openid or "").strip():
        return True
    return False


async def apply_activity_images(
    db: AsyncSession,
    activity: Activity,
    organizer: User,
    urls: list[str] | None,
) -> None:
    """设置活动图片并触发审核；``urls`` 为 ``[]`` 时清空。"""
    if urls is None:
        return
    if not urls:
        activity.cover_image_url = None
        activity.images = None
        activity.images_audit_status = IMAGES_AUDIT_NONE
        activity.images_audit_updated_at = datetime.now(UTC)
        return

    validated = validate_activity_image_urls(organizer.id, urls)
    if not validated:
        activity.cover_image_url = None
        activity.images = None
        activity.images_audit_status = IMAGES_AUDIT_NONE
        activity.images_audit_updated_at = datetime.now(UTC)
        return

    activity.cover_image_url = validated[0]
    activity.images = validated
    activity.images_audit_status = IMAGES_AUDIT_PENDING
    activity.images_audit_updated_at = datetime.now(UTC)

    audit = ActivityMediaAudit(
        activity_id=activity.id,
        user_id=organizer.id,
        status=IMAGES_AUDIT_PENDING,
        image_urls=validated,
        trace_entries=[],
    )
    db.add(audit)
    await db.flush()

    if _should_auto_pass_media_check(organizer):
        await _mark_audit_passed(db, audit, activity)
        return

    trace_entries: list[dict] = []
    openid = (organizer.mp_openid or "").strip()
    for idx, url in enumerate(validated):
        trace_id = await media_check_async(
            media_url=resolve_bos_read_url(url) or url,
            openid=openid,
            scene=SCENE_FORUM,
        )
        trace_entries.append(
            {
                "index": idx,
                "url": url,
                "trace_id": trace_id,
                "status": IMAGES_AUDIT_PENDING if trace_id else IMAGES_AUDIT_PASS,
            }
        )
    audit.trace_entries = trace_entries
    await _finalize_audit_if_ready(db, audit, activity)


async def maybe_expire_pending_activity_images(
    db: AsyncSession, activity: Activity
) -> bool:
    """pending 超过超时时间则视为 reject；返回是否发生变更。"""
    if activity.images_audit_status != IMAGES_AUDIT_PENDING:
        return False
    updated_at = to_utc_optional(activity.images_audit_updated_at)
    if updated_at is None:
        return False
    deadline = updated_at + timedelta(minutes=PENDING_TIMEOUT_MINUTES)
    if datetime.now(UTC) <= deadline:
        return False

    audit = await db.scalar(
        select(ActivityMediaAudit)
        .where(
            ActivityMediaAudit.activity_id == activity.id,
            ActivityMediaAudit.status == IMAGES_AUDIT_PENDING,
        )
        .order_by(ActivityMediaAudit.id.desc())
        .limit(1)
    )
    if audit:
        await _mark_audit_rejected(db, audit, activity, reject_index=None)
    else:
        activity.images_audit_status = IMAGES_AUDIT_REJECT
        activity.images_audit_updated_at = datetime.now(UTC)
    return True


async def handle_wechat_media_check_callback(
    db: AsyncSession, *, trace_id: str, suggest: str, label: int | None = None
) -> bool:
    """微信 ``wxa_media_check`` 回调；返回是否命中记录。"""
    tid = (trace_id or "").strip()
    if not tid:
        return False

    audits = (
        await db.execute(
            select(ActivityMediaAudit).where(ActivityMediaAudit.status == IMAGES_AUDIT_PENDING)
        )
    ).scalars().all()

    target_audit: ActivityMediaAudit | None = None
    target_entry: dict | None = None
    for audit in audits:
        entries = list(audit.trace_entries or [])
        for entry in entries:
            if str(entry.get("trace_id") or "") == tid:
                target_audit = audit
                target_entry = entry
                break
        if target_audit:
            break

    if not target_audit or not target_entry:
        logger.info("media_check callback trace_id=%s not matched", tid)
        return False

    suggest_norm = (suggest or "").strip().lower()
    entry_status = (
        IMAGES_AUDIT_REJECT if suggest_norm in _RISKY_SUGGESTS else IMAGES_AUDIT_PASS
    )
    target_entry["status"] = entry_status
    if label is not None:
        target_entry["label"] = label

    entries = list(target_audit.trace_entries or [])
    for i, entry in enumerate(entries):
        if str(entry.get("trace_id") or "") == tid:
            entries[i] = target_entry
            break
    target_audit.trace_entries = entries

    activity = await db.scalar(
        select(Activity).where(Activity.id == target_audit.activity_id)
    )
    if not activity:
        return True

    if entry_status == IMAGES_AUDIT_REJECT:
        reject_index = int(target_entry.get("index") or 0)
        await _mark_audit_rejected(db, target_audit, activity, reject_index=reject_index)
        return True

    await _finalize_audit_if_ready(db, target_audit, activity)
    return True


async def _finalize_audit_if_ready(
    db: AsyncSession, audit: ActivityMediaAudit, activity: Activity
) -> None:
    entries = list(audit.trace_entries or [])
    if not entries:
        await _mark_audit_passed(db, audit, activity)
        return
    if any(e.get("status") == IMAGES_AUDIT_REJECT for e in entries):
        reject_index = next(
            (int(e.get("index") or 0) for e in entries if e.get("status") == IMAGES_AUDIT_REJECT),
            0,
        )
        await _mark_audit_rejected(db, audit, activity, reject_index=reject_index)
        return
    if all(e.get("status") == IMAGES_AUDIT_PASS for e in entries):
        await _mark_audit_passed(db, audit, activity)


async def _mark_audit_passed(
    db: AsyncSession, audit: ActivityMediaAudit, activity: Activity
) -> None:
    audit.status = IMAGES_AUDIT_PASS
    activity.images_audit_status = IMAGES_AUDIT_PASS
    activity.images_audit_updated_at = datetime.now(UTC)


async def _mark_audit_rejected(
    db: AsyncSession,
    audit: ActivityMediaAudit,
    activity: Activity,
    *,
    reject_index: int | None,
) -> None:
    audit.status = IMAGES_AUDIT_REJECT
    audit.reject_index = reject_index
    activity.images_audit_status = IMAGES_AUDIT_REJECT
    activity.images_audit_updated_at = datetime.now(UTC)
