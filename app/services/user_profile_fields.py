"""从 User ORM 映射 bio/tags：供 GET /me、GET /users/:id/public、活动详情 organizer 共用，避免同源字段不一致。"""

from app.models.user import User


def bio_from_user(user: User | None) -> str:
    if user is None:
        return ""
    return (user.bio or "").strip()


def tags_from_user(user: User | None) -> list[str]:
    if user is None:
        return []
    raw = user.tags
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if x is not None]
