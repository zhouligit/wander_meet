"""用户资料完整度（登录后极简引导）。"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from fastapi import HTTPException

from app.models.user import User
from app.schemas.auth import LoginUser
from app.services.bos_storage import resolve_bos_read_url
from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z

_AUTO_NICKNAME_RE = re.compile(r"^旅人.{1,28}$")

PROFILE_INCOMPLETE_DETAIL = "请先完善资料"


def is_auto_nickname(nickname: str | None) -> bool:
    n = (nickname or "").strip()
    if not n:
        return True
    return bool(_AUTO_NICKNAME_RE.match(n))


def birth_date_for_api(user: User) -> str | None:
    if user.birth_date is None:
        return None
    return user.birth_date.isoformat()


def parse_birth_date(value: str) -> date:
    s = (value or "").strip()
    if not s:
        raise ValueError("birthDate is required")
    try:
        parsed = date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError("birthDate must be YYYY-MM-DD") from exc
    today = datetime.now(UTC).date()
    if parsed > today:
        raise ValueError("birthDate cannot be in the future")
    if parsed.year < 1900:
        raise ValueError("birthDate is invalid")
    return parsed


def profile_completion_errors(user: User) -> list[str]:
    errs: list[str] = []
    if is_auto_nickname(user.nickname):
        errs.append("请填写昵称（系统默认昵称不可用）")
    return errs


def assert_user_profile_complete(user: User) -> None:
    """报名、进群、发活动等需完整资料的操作前调用。"""
    if not profile_is_complete(user):
        raise HTTPException(status_code=403, detail=PROFILE_INCOMPLETE_DETAIL)


def profile_is_complete(user: User) -> bool:
    """资料是否已满足门槛：有效昵称（非系统默认「旅人xxxx」）。"""
    return not profile_completion_errors(user)


def build_login_user(user: User) -> LoginUser:
    g = user.gender
    if g is not None and g not in ("male", "female", "unspecified"):
        g = None
    return LoginUser(
        userId=f"u_{user.id}",
        nickname=user.nickname,
        avatarUrl=resolve_bos_read_url(user.avatar_url),
        gender=g,
        status=user.status,
        birthDate=birth_date_for_api(user),
        profileComplete=profile_is_complete(user),
        onboardingCompletedAt=datetime_to_rfc3339_utc_z(user.onboarding_completed_at),
    )
