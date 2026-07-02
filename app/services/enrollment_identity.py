"""活动实名报名信息：校验、脱敏、写入与修改窗口。"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from fastapi import HTTPException

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.user import User
from app.services.activity_update import activity_has_started
from app.services.user_phone_bind import assert_user_phone_bound, mask_user_phone, user_has_phone

_ID_CARD_RE = re.compile(r"^\d{17}[\dX]$")
_NAME_RE = re.compile(r"^[\u4e00-\u9fff·A-Za-z\s]{2,32}$")
_ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_ID_CHECK_MAP = "10X98765432"


def validate_participant_name(raw: str) -> str:
    name = (raw or "").strip()
    if len(name) < 2 or len(name) > 32:
        raise HTTPException(status_code=400, detail="姓名需 2～32 字")
    if not _NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="姓名格式不正确")
    return name


def validate_cn_id_card(raw: str) -> str:
    s = (raw or "").strip().upper()
    if len(s) != 18 or not _ID_CARD_RE.match(s):
        raise HTTPException(status_code=400, detail="身份证号格式不正确")
    total = sum(int(s[i]) * _ID_WEIGHTS[i] for i in range(17))
    if _ID_CHECK_MAP[total % 11] != s[17]:
        raise HTTPException(status_code=400, detail="身份证号格式不正确")
    return s


def normalize_enroll_identity_payload(
    participant_name: str | None,
    id_card_number: str | None,
    *,
    required: bool,
) -> tuple[str | None, str | None]:
    name_raw = (participant_name or "").strip()
    id_raw = (id_card_number or "").strip()
    if not name_raw and not id_raw:
        if required:
            raise HTTPException(status_code=400, detail="请填写姓名与身份证号")
        return None, None
    if not name_raw or not id_raw:
        raise HTTPException(status_code=400, detail="请填写姓名与身份证号")
    return validate_participant_name(name_raw), validate_cn_id_card(id_raw)


def mask_id_card(id_card: str) -> str:
    s = (id_card or "").strip()
    if len(s) < 8:
        return "****" if s else ""
    return f"{s[:6]}********{s[-4:]}"


def mask_phone_str(phone: str) -> str:
    p = (phone or "").strip()
    if len(p) >= 11:
        return f"{p[:3]}****{p[-4:]}"
    return ""


def can_edit_enrollment_identity(activity: Activity, now_utc: datetime | None = None) -> bool:
    if not activity.require_enrollment_identity:
        return False
    now_utc = now_utc or datetime.now(UTC)
    return not activity_has_started(activity, now_utc)


def apply_enrollment_identity(
    enrollment: ActivityEnrollment,
    user: User,
    participant_name: str,
    id_card_number: str,
) -> None:
    assert_user_phone_bound(user)
    enrollment.participant_name = participant_name
    enrollment.id_card_number = id_card_number
    enrollment.participant_phone = user.phone
    user.enrollment_identity_name = participant_name
    user.enrollment_identity_id_card = id_card_number


def enrollment_identity_prefill(user: User) -> dict[str, str]:
    return {
        "participantName": (user.enrollment_identity_name or "").strip(),
        "idCardNumber": (user.enrollment_identity_id_card or "").strip(),
        "phoneMasked": mask_user_phone(user) if user_has_phone(user) else "",
    }


def build_my_enrollment(
    enrollment: ActivityEnrollment | None,
    activity: Activity,
    now_utc: datetime | None = None,
):
    from app.schemas.activity import MyEnrollment, MyEnrollmentIdentity

    if enrollment is None or enrollment.status != "joined":
        return None
    identity = None
    if activity.require_enrollment_identity:
        identity = MyEnrollmentIdentity(
            participantName=(enrollment.participant_name or "").strip(),
            idCardMasked=mask_id_card(enrollment.id_card_number or ""),
            phoneMasked=mask_phone_str(enrollment.participant_phone or ""),
            canEditIdentity=can_edit_enrollment_identity(activity, now_utc),
        )
    return MyEnrollment(status=enrollment.status, identity=identity)


def member_identity_for_organizer(
    enrollment: ActivityEnrollment,
    *,
    show: bool,
):
    from app.schemas.activity import ActivityMemberIdentity

    if not show or not (enrollment.participant_name or "").strip():
        return None
    return ActivityMemberIdentity(
        participantName=enrollment.participant_name or "",
        idCardMasked=mask_id_card(enrollment.id_card_number or ""),
        phoneMasked=mask_phone_str(enrollment.participant_phone or ""),
    )
