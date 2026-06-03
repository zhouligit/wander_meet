"""PRD 裂变与信任 API（对齐小程序 ``wandermeet.js``）。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.db.session import get_db_session
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.growth_trust import (
    ActivityCheckin,
    ActivityExposureBoost,
    ActivityMeetReview,
    PhotoVerification,
    ReferralBinding,
    UserBadge,
    UserEntitlement,
    UserSafetyAck,
)
from app.models.user import User
from app.models.user_verification import UserVerification
from app.schemas.common import APIResponse
from app.schemas.growth_trust import (
    BadgeVisibilityData,
    BadgeVisibilityRequest,
    CheckinData,
    CheckinRequest,
    EntitlementItem,
    EntitlementsData,
    MeetHistoryData,
    MeetHistoryItem,
    MeetReviewCandidate,
    MeetReviewCandidatesData,
    MeetReviewSubmitRequest,
    OrganizerExposureData,
    PendingCheckinItem,
    PendingCheckinsData,
    PhotoVerificationStatusData,
    PhotoVerificationSubmitRequest,
    PhotoVerificationSummary,
    PhotoVerificationUploadData,
    PinActivityData,
    RealnameVerificationSummary,
    ReferralBindRequest,
    ReferralBindingData,
    ReferralData,
    ReferralRecordItem,
    SafetyAckData,
    SafetyAckRequest,
    SafetyGuideData,
    SafetyGuideSection,
    ShowMeetCountData,
    ShowMeetCountRequest,
    TrustBadgeItem,
    TrustData,
)
from app.services.activity_query import effective_activity_status
from app.services.bos_storage import (
    BosNotConfiguredError,
    put_photo_verify_bytes,
    validate_stored_chat_image_url,
    validate_stored_photo_selfie_url,
)
from app.services.city_hall import EVENT_ACTIVITY_KIND, is_city_hall_activity
from app.services.content_moderation import assert_text_content_safe
from app.services.wechat_content_security import SCENE_COMMENT
from app.services.growth_trust import (
    MEET_REVIEW_TAGS,
    ORGANIZER_EXPOSURE_TIERS,
    REFERRAL_TIERS,
    SAFETY_GUIDE_SECTIONS,
    _mask_nickname,
    _parse_activity_id,
    _parse_uid,
    _uid_str,
    bind_referral_code,
    checkin_window,
    count_qualified_referrals,
    get_or_create_referral_code,
    get_or_create_trust_profile,
    grant_pending_referral_rewards,
    next_tier_progress,
    process_successful_meet_pair,
    sync_trust_level,
    trust_score_summary,
)
from app.services.user_profile_fields import bio_from_user, tags_from_user

me_router = APIRouter(prefix="/me", tags=["growth-trust"])
act_router = APIRouter(prefix="/activities", tags=["growth-trust"])
content_router = APIRouter(tags=["growth-trust"])


@me_router.get("/referral")
async def get_my_referral(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ReferralData]:
    await grant_pending_referral_rewards(db)
    ref = await get_or_create_referral_code(db, current_user.id)
    qualified = await count_qualified_referrals(db, current_user.id)
    pending = int(
        await db.scalar(
            select(func.count(ReferralBinding.id)).where(
                ReferralBinding.inviter_id == current_user.id,
                ReferralBinding.status == "pending",
            )
        )
        or 0
    )
    next_tier, progress, _ = next_tier_progress(qualified, REFERRAL_TIERS)
    tp = await get_or_create_trust_profile(db, current_user.id)

    bindings = (
        await db.execute(
            select(ReferralBinding)
            .where(ReferralBinding.inviter_id == current_user.id)
            .order_by(ReferralBinding.id.desc())
            .limit(20)
        )
    ).scalars().all()
    invitee_ids = [b.invitee_id for b in bindings]
    users_map: dict[int, User] = {}
    if invitee_ids:
        users = (
            await db.execute(select(User).where(User.id.in_(invitee_ids)))
        ).scalars().all()
        users_map = {u.id: u for u in users}

    records = [
        ReferralRecordItem(
            inviteeNickname=_mask_nickname(
                (users_map[b.invitee_id].nickname if b.invitee_id in users_map else None) or "新用户"
            ),
            status=b.status,
            qualifiedAction=b.qualified_action,
            createdAt=b.created_at,
            qualifiedAt=b.qualified_at,
        )
        for b in bindings
    ]

    return APIResponse(
        data=ReferralData(
            code=ref.code,
            sharePath=f"/pages/entry/entry?inv={ref.code}",
            qualifiedCount=qualified,
            pendingCount=pending,
            photoVerified=tp.photo_verified,
            nextTier=next_tier,
            nextTierProgress=progress,
            tiers=REFERRAL_TIERS,
            records=records,
        )
    )


@me_router.post("/referral/bind")
async def post_referral_bind(
    payload: ReferralBindRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ReferralBindingData]:
    binding = await bind_referral_code(db, current_user, payload.code)
    return APIResponse(
        data=ReferralBindingData(
            status=binding.status,
            inviterId=_uid_str(binding.inviter_id),
        )
    )


@me_router.get("/entitlements")
async def get_my_entitlements(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[EntitlementsData]:
    rows = (
        await db.execute(
            select(UserEntitlement)
            .where(UserEntitlement.user_id == current_user.id)
            .order_by(UserEntitlement.id.desc())
        )
    ).scalars().all()
    items = [
        EntitlementItem(
            id=f"ent_{r.id}",
            entitlementType=r.entitlement_type,
            startsAt=r.starts_at,
            expiresAt=r.expires_at,
            pinQuotaRemaining=r.pin_quota_remaining or 0,
            source=r.source,
        )
        for r in rows
    ]
    return APIResponse(data=EntitlementsData(list=items))


@me_router.post("/activities/{activity_id}/pin")
async def pin_my_activity(
    activity_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PinActivityData]:
    aid = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == aid))
    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在")
    if activity.organizer_id != current_user.id:
        raise HTTPException(status_code=400, detail="只能置顶自己组织的活动")
    if is_city_hall_activity(activity):
        raise HTTPException(status_code=400, detail="城市大群不支持置顶")

    now = datetime.now(UTC)
    ent = (
        await db.execute(
            select(UserEntitlement)
            .where(
                UserEntitlement.user_id == current_user.id,
                UserEntitlement.expires_at > now,
                UserEntitlement.pin_quota_remaining > 0,
            )
            .order_by(UserEntitlement.expires_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not ent:
        raise HTTPException(status_code=400, detail="暂无可用置顶次数")

    ent.pin_quota_remaining -= 1
    pinned_until = now + timedelta(days=1)
    db.add(
        ActivityExposureBoost(
            activity_id=aid,
            user_id=current_user.id,
            boost_type="pin",
            weight=100,
            starts_at=now,
            ends_at=pinned_until,
        )
    )
    await db.commit()
    return APIResponse(
        data=PinActivityData(activityId=f"act_{aid}", pinnedUntil=pinned_until)
    )


@me_router.get("/meet-checkins/pending")
async def get_pending_meet_checkins(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PendingCheckinsData]:
    now = datetime.now(UTC)
    rows = (
        await db.execute(
            select(Activity, ActivityEnrollment)
            .join(
                ActivityEnrollment,
                ActivityEnrollment.activity_id == Activity.id,
            )
            .where(
                ActivityEnrollment.user_id == current_user.id,
                ActivityEnrollment.status == "joined",
                Activity.activity_kind == EVENT_ACTIVITY_KIND,
                Activity.activity_status != "cancelled",
            )
        )
    ).all()

    items: list[PendingCheckinItem] = []
    for activity, _en in rows:
        eff = effective_activity_status(activity, now)
        if eff == "cancelled":
            continue
        open_, _, window_end = checkin_window(activity, now)
        if not open_:
            continue
        checked = await db.scalar(
            select(ActivityCheckin.id).where(
                ActivityCheckin.activity_id == activity.id,
                ActivityCheckin.user_id == current_user.id,
            )
        )
        if checked:
            continue
        items.append(
            PendingCheckinItem(
                activityId=f"act_{activity.id}",
                title=activity.title,
                startAt=activity.start_at,
                locationName=activity.location_name,
                checkinOpen=True,
                checkedIn=False,
                windowEnd=window_end,
            )
        )
    return APIResponse(data=PendingCheckinsData(list=items))


@act_router.post("/{activity_id}/checkin")
async def checkin_activity(
    activity_id: str,
    payload: CheckinRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[CheckinData]:
    aid = _parse_activity_id(activity_id)
    activity = await db.scalar(select(Activity).where(Activity.id == aid))
    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在")
    if is_city_hall_activity(activity):
        raise HTTPException(status_code=400, detail="城市大群不支持打卡")

    en = await db.scalar(
        select(ActivityEnrollment.id).where(
            ActivityEnrollment.activity_id == aid,
            ActivityEnrollment.user_id == current_user.id,
            ActivityEnrollment.status == "joined",
        )
    )
    if not en:
        raise HTTPException(status_code=403, detail="未报名该活动")

    open_, _, _ = checkin_window(activity)
    if not open_:
        raise HTTPException(status_code=400, detail="当前不在打卡时间窗口内")

    existing = await db.scalar(
        select(ActivityCheckin).where(
            ActivityCheckin.activity_id == aid,
            ActivityCheckin.user_id == current_user.id,
        )
    )
    if existing:
        return APIResponse(
            data=CheckinData(
                activityId=f"act_{aid}",
                checkedInAt=existing.checked_in_at,
            )
        )

    photo_url = None
    if payload.photoUrl:
        photo_url = validate_stored_chat_image_url(payload.photoUrl, current_user.id)

    now = datetime.now(UTC)
    row = ActivityCheckin(
        activity_id=aid,
        user_id=current_user.id,
        checked_in_at=now,
        photo_url=photo_url,
    )
    db.add(row)
    await db.commit()
    return APIResponse(
        data=CheckinData(activityId=f"act_{aid}", checkedInAt=now)
    )


@act_router.get("/{activity_id}/meet-review/candidates")
async def meet_review_candidates(
    activity_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MeetReviewCandidatesData]:
    aid = _parse_activity_id(activity_id)
    my_checkin = await db.scalar(
        select(ActivityCheckin.id).where(
            ActivityCheckin.activity_id == aid,
            ActivityCheckin.user_id == current_user.id,
        )
    )
    if not my_checkin:
        raise HTTPException(status_code=400, detail="请先完成到场打卡")

    checked_user_ids = (
        await db.execute(
            select(ActivityCheckin.user_id).where(ActivityCheckin.activity_id == aid)
        )
    ).scalars().all()
    reviewed_ids = (
        await db.execute(
            select(ActivityMeetReview.to_user_id).where(
                ActivityMeetReview.activity_id == aid,
                ActivityMeetReview.from_user_id == current_user.id,
            )
        )
    ).scalars().all()
    reviewed_set = set(reviewed_ids)

    candidate_ids = [
        uid
        for uid in checked_user_ids
        if uid != current_user.id and uid not in reviewed_set
    ]
    users_map: dict[int, User] = {}
    if candidate_ids:
        users = (
            await db.execute(select(User).where(User.id.in_(candidate_ids)))
        ).scalars().all()
        users_map = {u.id: u for u in users}

    items = [
        MeetReviewCandidate(
            userId=_uid_str(uid),
            nickname=users_map[uid].nickname if uid in users_map else "参与者",
            avatarUrl=users_map[uid].avatar_url if uid in users_map else None,
        )
        for uid in candidate_ids
    ]
    return APIResponse(data=MeetReviewCandidatesData(list=items))


@act_router.post("/{activity_id}/meet-review")
async def submit_meet_review(
    activity_id: str,
    payload: MeetReviewSubmitRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    aid = _parse_activity_id(activity_id)
    to_uid = _parse_uid(payload.toUserId)

    my_checkin = await db.scalar(
        select(ActivityCheckin.id).where(
            ActivityCheckin.activity_id == aid,
            ActivityCheckin.user_id == current_user.id,
        )
    )
    if not my_checkin:
        raise HTTPException(status_code=400, detail="请先完成到场打卡")

    their_checkin = await db.scalar(
        select(ActivityCheckin.id).where(
            ActivityCheckin.activity_id == aid,
            ActivityCheckin.user_id == to_uid,
        )
    )
    if not their_checkin:
        raise HTTPException(status_code=400, detail="对方尚未打卡")

    dup = await db.scalar(
        select(ActivityMeetReview.id).where(
            ActivityMeetReview.activity_id == aid,
            ActivityMeetReview.from_user_id == current_user.id,
            ActivityMeetReview.to_user_id == to_uid,
        )
    )
    if dup:
        raise HTTPException(status_code=400, detail="已评价过该用户")

    tags = [t for t in (payload.tags or [])[:3] if t in MEET_REVIEW_TAGS]
    comment = (payload.comment or "")[:50] or None
    if comment:
        await assert_text_content_safe(current_user, comment, scene=SCENE_COMMENT)

    db.add(
        ActivityMeetReview(
            activity_id=aid,
            from_user_id=current_user.id,
            to_user_id=to_uid,
            met=payload.met,
            tags=tags or None,
            comment=comment,
        )
    )
    await db.commit()
    if payload.met:
        await process_successful_meet_pair(db, aid, current_user.id, to_uid)
    return APIResponse(data={"ok": True})


@me_router.get("/meet-history")
async def get_meet_history(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[MeetHistoryData]:
    checkins = (
        await db.execute(
            select(ActivityCheckin).where(ActivityCheckin.user_id == current_user.id)
        )
    ).scalars().all()
    activity_ids = list({c.activity_id for c in checkins})
    if not activity_ids:
        return APIResponse(data=MeetHistoryData(list=[]))

    activities = (
        await db.execute(select(Activity).where(Activity.id.in_(activity_ids)))
    ).scalars().all()
    act_map = {a.id: a for a in activities}

    items: list[MeetHistoryItem] = []
    for aid in activity_ids:
        act = act_map.get(aid)
        checked = any(c.activity_id == aid for c in checkins)
        my_reviews = (
            await db.execute(
                select(ActivityMeetReview).where(
                    ActivityMeetReview.activity_id == aid,
                    ActivityMeetReview.from_user_id == current_user.id,
                )
            )
        ).scalars().all()
        others_count = int(
            await db.scalar(
                select(func.count(ActivityCheckin.id)).where(
                    ActivityCheckin.activity_id == aid,
                    ActivityCheckin.user_id != current_user.id,
                )
            )
            or 0
        )
        reviews_done = len(my_reviews)
        success = (
            checked
            and reviews_done >= others_count
            and any(r.met for r in my_reviews)
        )
        items.append(
            MeetHistoryItem(
                activityId=f"act_{aid}",
                title=act.title if act else "活动",
                startAt=act.start_at if act else None,
                success=success,
                checkedIn=checked,
            )
        )
    return APIResponse(data=MeetHistoryData(list=items))


@me_router.get("/trust")
async def get_my_trust(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[TrustData]:
    tp = await sync_trust_level(db, current_user)
    photo_row = (
        await db.execute(
            select(PhotoVerification)
            .where(PhotoVerification.user_id == current_user.id)
            .order_by(PhotoVerification.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    photo_summary = PhotoVerificationSummary(
        status=photo_row.status if photo_row else None,
        rejectReason=photo_row.reject_reason if photo_row else None,
        submittedAt=photo_row.submitted_at if photo_row else None,
    )
    realname = await db.scalar(
        select(UserVerification).where(UserVerification.user_id == current_user.id)
    )
    badges = (
        await db.execute(
            select(UserBadge).where(UserBadge.user_id == current_user.id)
        )
    ).scalars().all()
    qualified = await count_qualified_referrals(db, current_user.id)
    has_profile = bool(
        current_user.avatar_url
        and current_user.nickname
        and bio_from_user(current_user)
        and len(tags_from_user(current_user)) >= 1
    )
    return APIResponse(
        data=TrustData(
            trustLevel=tp.trust_level,
            trustScoreSummary=trust_score_summary(tp.trust_score),
            meetCount=tp.meet_count,
            showMeetCount=tp.show_meet_count,
            photoVerified=tp.photo_verified,
            photoVerification=photo_summary,
            realnameVerification=RealnameVerificationSummary(
                status=realname.status if realname else None,
            ),
            profileComplete=has_profile,
            qualifiedReferrals=qualified,
            badges=[
                TrustBadgeItem(
                    badgeId=b.badge_id,
                    grantedAt=b.granted_at,
                    visible=b.visible,
                )
                for b in badges
            ],
        )
    )


@me_router.post("/photo-verification")
async def submit_photo_verification(
    payload: PhotoVerificationSubmitRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PhotoVerificationStatusData]:
    selfie = (payload.selfieUrl or "").strip()
    if not selfie:
        raise HTTPException(status_code=400, detail="selfieUrl required")
    if selfie.startswith("http://") or selfie.startswith("https://"):
        selfie = validate_stored_photo_selfie_url(selfie, current_user.id)
    else:
        raise HTTPException(
            status_code=400,
            detail="请先通过 /me/photo-verification/upload 上传自拍",
        )

    pending = await db.scalar(
        select(PhotoVerification).where(
            PhotoVerification.user_id == current_user.id,
            PhotoVerification.status == "pending",
        )
    )
    if pending:
        raise HTTPException(status_code=400, detail="已有审核中的申请")

    now = datetime.now(UTC)
    row = PhotoVerification(
        user_id=current_user.id,
        selfie_url=selfie,
        status="pending",
    )
    db.add(row)
    await db.commit()
    return APIResponse(
        data=PhotoVerificationStatusData(status="pending", submittedAt=now)
    )


@me_router.post("/photo-verification/upload")
async def upload_photo_verification(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PhotoVerificationUploadData]:
    body = await file.read()
    file_ext = None
    if file.filename and "." in file.filename:
        file_ext = file.filename.rsplit(".", 1)[-1]
    try:
        public_url = await asyncio.to_thread(
            put_photo_verify_bytes,
            user_id=current_user.id,
            data=body,
            content_type=file.content_type or "image/jpeg",
            file_ext=file_ext,
        )
    except BosNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return APIResponse(data=PhotoVerificationUploadData(selfieUrl=public_url))


@me_router.get("/photo-verification")
async def get_photo_verification(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[PhotoVerificationStatusData]:
    row = (
        await db.execute(
            select(PhotoVerification)
            .where(PhotoVerification.user_id == current_user.id)
            .order_by(PhotoVerification.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not row:
        return APIResponse(data=PhotoVerificationStatusData(status=None))
    return APIResponse(
        data=PhotoVerificationStatusData(
            status=row.status,
            rejectReason=row.reject_reason,
            submittedAt=row.submitted_at,
            reviewedAt=row.reviewed_at,
        )
    )


@me_router.post("/safety-ack")
async def post_safety_ack(
    payload: SafetyAckRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[SafetyAckData]:
    ack_type = (payload.ackType or "enroll_first").strip() or "enroll_first"
    existing = await db.scalar(
        select(UserSafetyAck).where(
            UserSafetyAck.user_id == current_user.id,
            UserSafetyAck.ack_type == ack_type,
        )
    )
    if existing:
        return APIResponse(
            data=SafetyAckData(ackType=ack_type, ackAt=existing.ack_at)
        )
    now = datetime.now(UTC)
    row = UserSafetyAck(user_id=current_user.id, ack_type=ack_type, ack_at=now)
    db.add(row)
    await db.commit()
    return APIResponse(data=SafetyAckData(ackType=ack_type, ackAt=now))


@content_router.get("/content/safety-guide")
async def get_safety_guide(
    _: User | None = Depends(get_optional_user),
) -> APIResponse[SafetyGuideData]:
    sections = [SafetyGuideSection(**s) for s in SAFETY_GUIDE_SECTIONS]
    return APIResponse(data=SafetyGuideData(format="sections", sections=sections))


@me_router.get("/organizer-exposure")
async def get_organizer_exposure(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[OrganizerExposureData]:
    qualified = await count_qualified_referrals(db, current_user.id)
    next_tier, progress, _ = next_tier_progress(qualified, ORGANIZER_EXPOSURE_TIERS)
    return APIResponse(
        data=OrganizerExposureData(
            qualifiedReferrals=qualified,
            nextTier=next_tier,
            nextTierProgress=progress,
            tiers=ORGANIZER_EXPOSURE_TIERS,
        )
    )


@me_router.patch("/badges/visibility")
async def patch_badge_visibility(
    payload: BadgeVisibilityRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[BadgeVisibilityData]:
    row = await db.scalar(
        select(UserBadge).where(
            UserBadge.user_id == current_user.id,
            UserBadge.badge_id == payload.badgeId,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="徽章不存在")
    row.visible = payload.visible
    await db.commit()
    return APIResponse(
        data=BadgeVisibilityData(badgeId=payload.badgeId, visible=row.visible)
    )


@me_router.patch("/trust/show-meet-count")
async def patch_show_meet_count(
    payload: ShowMeetCountRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ShowMeetCountData]:
    tp = await get_or_create_trust_profile(db, current_user.id)
    tp.show_meet_count = payload.showMeetCount
    await db.commit()
    return APIResponse(
        data=ShowMeetCountData(showMeetCount=tp.show_meet_count)
    )
