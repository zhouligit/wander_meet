"""用户资料完整度（登录后极简引导）。"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from app.models.user import User
from app.schemas.auth import LoginUser
from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z

_AUTO_NICKNAME_RE = re.compile(r"^旅人.{1,28}$")


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
    if user.gender not in ("male", "female"):
        errs.append("请选择性别（男或女）")
    if user.birth_date is None:
        errs.append("请选择出生日期")
    return errs


def profile_is_complete(user: User) -> bool:
    if user.onboarding_completed_at is None:
        return False
    return not profile_completion_errors(user)


def build_login_user(user: User) -> LoginUser:
    g = user.gender
    if g is not None and g not in ("male", "female", "unspecified"):
        g = None
    return LoginUser(
        userId=f"u_{user.id}",
        nickname=user.nickname,
        avatarUrl=user.avatar_url,
        gender=g,
        status=user.status,
        birthDate=birth_date_for_api(user),
        profileComplete=profile_is_complete(user),
        onboardingCompletedAt=datetime_to_rfc3339_utc_z(user.onboarding_completed_at),
    )
