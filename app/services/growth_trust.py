"""PRD 裂变与信任：邀请、权益、见面打卡互评、信任档案。"""

from __future__ import annotations

import json
import logging
import random
import string
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.growth_trust import (
    ActivityCheckin,
    ActivityExposureBoost,
    ActivityMeetReview,
    PhotoVerification,
    ReferralBinding,
    ReferralCode,
    UserBadge,
    UserEntitlement,
    UserSafetyAck,
    UserTrustProfile,
)
from app.models.user import User
from app.models.user_verification import UserVerification
from app.services.activity_query import to_utc
from app.services.city_hall import CITY_HALL_ACTIVITY_KIND, EVENT_ACTIVITY_KIND
from app.services.user_profile_fields import bio_from_user, tags_from_user

logger = logging.getLogger(__name__)

REFERRAL_TIERS = [1, 3, 5, 10]
ORGANIZER_EXPOSURE_TIERS = [3, 5, 10]
QUALIFY_DAYS = 7
REWARD_DELAY_HOURS = 24
ENTITLEMENT_DAYS = {
    "premium_lite_3d": 3,
    "premium_std_7d": 7,
    "premium_std_15d": 15,
    "premium_std_30d": 30,
}
MEET_REVIEW_TAGS = frozenset(
    {"punctual", "friendly", "would_meet_again", "would_not_meet_again"}
)
TRUST_DM_MIN_SCORE = 400


def _uid_str(user_id: int) -> str:
    return f"u_{user_id}"


def _parse_uid(raw: str) -> int:
    s = (raw or "").strip()
    if s.startswith("u_"):
        s = s[2:]
    return int(s)


def _parse_activity_id(activity_id: str) -> int:
    s = activity_id[4:] if activity_id.startswith("act_") else activity_id
    return int(s)


def _mask_nickname(name: str) -> str:
    s = (name or "用户").strip()
    if len(s) <= 1:
        return f"{s}*"
    return f"{s[0]}**{s[-1]}"


def _add_days(base: datetime, days: int) -> datetime:
    return base + timedelta(days=days)


async def get_or_create_trust_profile(db: AsyncSession, user_id: int) -> UserTrustProfile:
    row = await db.scalar(select(UserTrustProfile).where(UserTrustProfile.user_id == user_id))
    if row:
        return row
    row = UserTrustProfile(user_id=user_id)
    db.add(row)
    await db.flush()
    return row


async def compute_trust_level(db: AsyncSession, user: User) -> str:
    tp = await get_or_create_trust_profile(db, user.id)
    has_profile = bool(
        user.avatar_url
        and user.nickname
        and bio_from_user(user)
        and len(tags_from_user(user)) >= 1
    )
    realname = await db.scalar(
        select(UserVerification.id).where(
            UserVerification.user_id == user.id,
            UserVerification.status == "approved",
        )
    )
    if realname:
        return "realname_verified"
    if tp.photo_verified:
        return "photo_verified"
    if has_profile:
        return "profile_complete"
    return "basic"


async def sync_trust_level(db: AsyncSession, user: User) -> UserTrustProfile:
    tp = await get_or_create_trust_profile(db, user.id)
    tp.trust_level = await compute_trust_level(db, user)
    tp.updated_at = datetime.now(UTC)
    return tp


def trust_score_summary(score: int) -> str:
    if score >= 700:
        return "良好"
    if score >= 400:
        return "一般"
    return "偏低"


async def _gen_unique_code(db: AsyncSession, user_id: int) -> str:
    base = f"WM{user_id:04d}"[-4:]
    for _ in range(20):
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        code = f"{base}{suffix}"[:8]
        exists = await db.scalar(select(ReferralCode.id).where(ReferralCode.code == code))
        if not exists:
            return code
    return f"WM{user_id % 10000:04d}{random.randint(10, 99)}"


async def get_or_create_referral_code(db: AsyncSession, user_id: int) -> ReferralCode:
    row = await db.scalar(select(ReferralCode).where(ReferralCode.user_id == user_id))
    if row:
        return row
    row = ReferralCode(user_id=user_id, code=await _gen_unique_code(db, user_id))
    db.add(row)
    await db.flush()
    return row


async def count_qualified_referrals(db: AsyncSession, inviter_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count(ReferralBinding.id)).where(
                ReferralBinding.inviter_id == inviter_id,
                ReferralBinding.status == "qualified",
            )
        )
        or 0
    )


def next_tier_progress(qualified: int, tiers: list[int]) -> tuple[int | None, float, int]:
    if qualified >= tiers[-1]:
        return None, 1.0, tiers[-1]
    next_tier = tiers[0]
    for t in tiers:
        if qualified < t:
            next_tier = t
            break
    prev = max([t for t in tiers if t <= qualified], default=0)
    span = next_tier - prev or next_tier
    progress = min(1.0, (qualified - prev) / span)
    return next_tier, progress, prev


async def grant_entitlement(
    db: AsyncSession,
    user_id: int,
    entitlement_type: str,
    source: str,
    source_ref_id: int | None = None,
    pin_quota: int = 0,
    *,
    photo_verified_bonus: bool = False,
) -> UserEntitlement:
    days = ENTITLEMENT_DAYS.get(entitlement_type, 7)
    if photo_verified_bonus:
        days = int(days * 1.2 + 0.999)
    now = datetime.now(UTC)
    active = (
        await db.execute(
            select(UserEntitlement)
            .where(
                UserEntitlement.user_id == user_id,
                UserEntitlement.expires_at > now,
            )
            .order_by(UserEntitlement.expires_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    base = active.expires_at if active else now
    row = UserEntitlement(
        user_id=user_id,
        entitlement_type=entitlement_type,
        starts_at=now,
        expires_at=_add_days(base, days),
        pin_quota_remaining=pin_quota,
        source=source,
        source_ref_id=source_ref_id,
    )
    db.add(row)
    await db.flush()
    return row


async def grant_badge(db: AsyncSession, user_id: int, badge_id: str) -> UserBadge | None:
    exists = await db.scalar(
        select(UserBadge.id).where(
            UserBadge.user_id == user_id,
            UserBadge.badge_id == badge_id,
        )
    )
    if exists:
        return None
    row = UserBadge(user_id=user_id, badge_id=badge_id, visible=True)
    db.add(row)
    await db.flush()
    return row


async def get_active_entitlement_summary(db: AsyncSession, user_id: int) -> dict | None:
    now = datetime.now(UTC)
    rows = (
        await db.execute(
            select(UserEntitlement)
            .where(
                UserEntitlement.user_id == user_id,
                UserEntitlement.expires_at > now,
            )
            .order_by(UserEntitlement.expires_at.desc())
        )
    ).scalars().all()
    if not rows:
        return None
    pin_quota = sum(r.pin_quota_remaining or 0 for r in rows)
    top = rows[0]
    tier = "lite" if "lite" in top.entitlement_type else "standard"
    return {
        "active": True,
        "tier": tier,
        "expiresAt": top.expires_at,
        "pinQuotaRemaining": pin_quota,
    }


async def get_visible_badge_ids(db: AsyncSession, user_id: int) -> list[str]:
    rows = (
        await db.execute(
            select(UserBadge.badge_id).where(
                UserBadge.user_id == user_id,
                UserBadge.visible.is_(True),
            )
        )
    ).scalars().all()
    return list(rows)


async def grant_inviter_rewards_for_qualified_count(
    db: AsyncSession, inviter_id: int, qualified_count: int, *, photo_verified: bool
) -> None:
    """邀请人有效邀请数达到阶梯时发放对应奖励（每个阶梯只在该人数首次达成时触发）。"""
    if qualified_count == 1:
        await grant_entitlement(
            db,
            inviter_id,
            "premium_std_7d",
            "referral",
            qualified_count,
            photo_verified_bonus=photo_verified,
        )
    elif qualified_count == 3:
        await grant_entitlement(
            db,
            inviter_id,
            "premium_std_15d",
            "referral",
            qualified_count,
            photo_verified_bonus=photo_verified,
        )
        await grant_badge(db, inviter_id, "referrer_guide")
    elif qualified_count == 5:
        await grant_entitlement(
            db,
            inviter_id,
            "premium_std_15d",
            "referral",
            qualified_count,
            pin_quota=1,
            photo_verified_bonus=photo_verified,
        )
    elif qualified_count == 10:
        await grant_entitlement(
            db,
            inviter_id,
            "premium_std_30d",
            "referral",
            qualified_count,
            photo_verified_bonus=photo_verified,
        )
        await grant_badge(db, inviter_id, "referrer_ambassador")
    if qualified_count in REFERRAL_TIERS:
        tp = await get_or_create_trust_profile(db, inviter_id)
        tp.trust_score = min(1000, tp.trust_score + 20)
        await db.flush()


async def grant_pending_referral_rewards(db: AsyncSession) -> None:
    """T+1：对已 qualified 且超过延迟时间的绑定发放邀请人阶梯奖励。"""
    cutoff = datetime.now(UTC) - timedelta(hours=REWARD_DELAY_HOURS)
    rows = (
        await db.execute(
            select(ReferralBinding).where(
                ReferralBinding.status == "qualified",
                ReferralBinding.reward_granted_at.is_(None),
                ReferralBinding.qualified_at <= cutoff,
            )
        )
    ).scalars().all()
    for binding in rows:
        inviter = await db.scalar(select(User).where(User.id == binding.inviter_id))
        if not inviter:
            continue
        tp = await get_or_create_trust_profile(db, inviter.id)
        qualified = await count_qualified_referrals(db, inviter.id)
        await grant_inviter_rewards_for_qualified_count(
            db, inviter.id, qualified, photo_verified=tp.photo_verified
        )
        binding.reward_granted_at = datetime.now(UTC)
    if rows:
        await db.commit()


async def on_qualified_action(db: AsyncSession, user_id: int, action: str) -> None:
    """用户加群或报名后尝试完成邀请有效动作。"""
    binding = await db.scalar(
        select(ReferralBinding).where(
            ReferralBinding.invitee_id == user_id,
            ReferralBinding.status == "pending",
        )
    )
    if not binding:
        return
    deadline = binding.created_at + timedelta(days=QUALIFY_DAYS)
    if datetime.now(UTC) > to_utc(deadline):
        binding.status = "expired"
        await db.commit()
        return
    binding.status = "qualified"
    binding.qualified_action = action
    binding.qualified_at = datetime.now(UTC)
    await grant_entitlement(db, user_id, "premium_lite_3d", "referral", binding.id)
    await grant_badge(db, user_id, "newcomer")
    tp = await get_or_create_trust_profile(db, user_id)
    tp.trust_score = min(1000, tp.trust_score + 20)
    user = await db.scalar(select(User).where(User.id == user_id))
    if user:
        await sync_trust_level(db, user)
    await db.commit()


async def bind_referral_code(db: AsyncSession, invitee: User, code: str) -> ReferralBinding:
    code_norm = (code or "").strip().upper()
    if not code_norm:
        raise HTTPException(status_code=400, detail="邀请码无效")
    existing = await db.scalar(
        select(ReferralBinding).where(ReferralBinding.invitee_id == invitee.id)
    )
    if existing:
        raise HTTPException(status_code=400, detail="已绑定邀请关系")
    ref = await db.scalar(select(ReferralCode).where(ReferralCode.code == code_norm))
    if not ref:
        raise HTTPException(status_code=400, detail="邀请码无效")
    if ref.user_id == invitee.id:
        raise HTTPException(status_code=400, detail="不能使用自己的邀请码")
    binding = ReferralBinding(
        inviter_id=ref.user_id,
        invitee_id=invitee.id,
        code=code_norm,
        status="pending",
    )
    db.add(binding)
    invitee.acquisition_source = f"referral:{code_norm}"
    await db.commit()
    await db.refresh(binding)
    return binding


def checkin_window(activity: Activity, now: datetime | None = None) -> tuple[bool, datetime, datetime]:
    now = now or datetime.now(UTC)
    start = to_utc(activity.start_at)
    window_start = start + timedelta(hours=2)
    if activity.end_at:
        end_at = to_utc(activity.end_at)
        window_end = min(end_at + timedelta(hours=24), start + timedelta(hours=72))
    else:
        window_end = start + timedelta(hours=48)
    open_ = window_start <= now <= window_end
    return open_, window_start, window_end


async def process_successful_meet_pair(
    db: AsyncSession, activity_id: int, user_a: int, user_b: int
) -> None:
    for uid in (user_a, user_b):
        rev = await db.scalar(
            select(ActivityMeetReview).where(
                ActivityMeetReview.activity_id == activity_id,
                ActivityMeetReview.from_user_id == uid,
                ActivityMeetReview.to_user_id == user_b if uid == user_a else user_a,
            )
        )
        if not rev or not rev.met:
            return
    for uid in (user_a, user_b):
        chk = await db.scalar(
            select(ActivityCheckin.id).where(
                ActivityCheckin.activity_id == activity_id,
                ActivityCheckin.user_id == uid,
            )
        )
        if not chk:
            return
    for uid in (user_a, user_b):
        tp = await get_or_create_trust_profile(db, uid)
        prev = tp.meet_count
        tp.meet_count += 1
        tp.trust_score = min(1000, tp.trust_score + 30)
        user = await db.scalar(select(User).where(User.id == uid))
        if user:
            await sync_trust_level(db, user)
        if prev == 0:
            await grant_badge(db, uid, "meet_first")
            await grant_entitlement(db, uid, "premium_std_7d", "meet", activity_id)
        elif tp.meet_count == 3:
            await grant_entitlement(db, uid, "premium_std_7d", "meet", activity_id)
        elif tp.meet_count == 5:
            await grant_badge(db, uid, "meet_regular")
    await db.commit()


async def can_initiate_dm(db: AsyncSession, user_id: int) -> bool:
    tp = await get_or_create_trust_profile(db, user_id)
    return tp.trust_score >= TRUST_DM_MIN_SCORE


SAFETY_GUIDE_SECTIONS = [
    {
        "title": "见面地点怎么选",
        "body": "优先地铁口、商场、连锁咖啡等人流较多的公共场所；首次见面避免私密场所或偏远地点。",
    },
    {
        "title": "独行赴约前告知亲友",
        "body": "把活动时间、地点、同行人数告诉可信赖的亲友；约定一个「平安报平安」的时间点。",
    },
    {
        "title": "费用 AA 与防诈骗",
        "body": "活动费用以现场 AA 为主；不要向陌生人预付大额费用或转账；遇到异常收费及时退出并举报。",
    },
    {
        "title": "不适时如何举报/拉黑",
        "body": "在活动详情或用户资料页可举报；私聊中遇到骚扰可拉黑。平台会处理违规账号。",
    },
    {
        "title": "平台能力说明",
        "body": "旅聚提供照片验证、实名认证（可选）、见面打卡与互评（不公开差评）、举报与拉黑等能力，帮助你更安心地同城社交。",
    },
]


async def approve_photo_verification(
    db: AsyncSession,
    verification_id: int,
    reviewer_id: int,
) -> PhotoVerification:
    row = await db.scalar(
        select(PhotoVerification).where(PhotoVerification.id == verification_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="验证记录不存在")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="该记录已审核")
    now = datetime.now(UTC)
    row.status = "approved"
    row.reviewer_id = reviewer_id
    row.reviewed_at = now
    row.reject_reason = None
    tp = await get_or_create_trust_profile(db, row.user_id)
    tp.photo_verified = True
    tp.trust_score = min(1000, tp.trust_score + 150)
    user = await db.scalar(select(User).where(User.id == row.user_id))
    if user:
        await sync_trust_level(db, user)
    await db.flush()
    return row


async def reject_photo_verification(
    db: AsyncSession,
    verification_id: int,
    reviewer_id: int,
    reason: str,
) -> PhotoVerification:
    row = await db.scalar(
        select(PhotoVerification).where(PhotoVerification.id == verification_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="验证记录不存在")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="该记录已审核")
    now = datetime.now(UTC)
    row.status = "rejected"
    row.reviewer_id = reviewer_id
    row.reviewed_at = now
    row.reject_reason = (reason or "请重新拍摄").strip()[:256]
    await db.flush()
    return row


async def build_premium_data(db: AsyncSession, user_id: int) -> dict:
    ent = await get_active_entitlement_summary(db, user_id)
    badges = await get_visible_badge_ids(db, user_id)
    if not ent:
        return {
            "enabled": False,
            "sku": [],
            "entitlement": {"active": False, "badges": badges},
        }
    return {
        "enabled": True,
        "sku": [],
        "entitlement": {**ent, "badges": badges},
    }


async def build_public_trust_fields(db: AsyncSession, target: User) -> dict:
    tp = await sync_trust_level(db, target)
    badges = await get_visible_badge_ids(db, target.id)
    ent = await get_active_entitlement_summary(db, target.id)
    meet_count = tp.meet_count if tp.show_meet_count else 0
    return {
        "trustLevel": tp.trust_level,
        "photoVerified": tp.photo_verified,
        "meetCount": meet_count,
        "showMeetCount": tp.show_meet_count,
        "badges": badges,
        "premiumBadge": bool(ent and ent.get("active")),
    }
