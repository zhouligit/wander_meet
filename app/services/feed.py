"""同城动态：V0.5 活动态、V1 同城广场、V2 关注与话题。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.feed import Post, PostComment, PostLike, UserFollow
from app.models.user import User
from app.models.user_block import UserBlock
from app.services.activity_query import effective_activity_status, to_utc
from app.services.bos_storage import validate_stored_feed_image_url
from app.services.city_hall import EVENT_ACTIVITY_KIND, is_city_hall_activity
from app.services.local_text_content_filter import local_text_blocked_reason
from app.services.content_moderation import assert_image_urls_safe, assert_text_content_safe
from app.services.wechat_content_security import SCENE_COMMENT, SCENE_SOCIAL
from app.services.dm_relationship import either_blocked
from app.services.growth_trust import build_public_trust_fields
from app.services.user_profile_fields import bio_from_user

POST_KIND_CITY = "city"
POST_KIND_ACTIVITY = "activity"
MAX_CONTENT_LEN = 2000
MAX_COMMENT_LEN = 500
MAX_POSTS_PER_DAY = 20
ACTIVITY_POST_HOURS_AFTER_END = 72
ALLOWED_TOPICS = frozenset({"weekend", "city_move", "buddy", "activity_recap"})

TOPIC_META = [
    {"id": "weekend", "label": "周末出门"},
    {"id": "city_move", "label": "换城市了"},
    {"id": "buddy", "label": "找搭子"},
    {"id": "activity_recap", "label": "活动复盘"},
]


def _uid_str(user_id: int) -> str:
    return f"u_{user_id}"


def _parse_uid(raw: str) -> int:
    s = (raw or "").strip()
    if s.startswith("u_"):
        s = s[2:]
    return int(s)


def _parse_post_id(post_id: str) -> int:
    s = post_id[5:] if post_id.startswith("post_") else post_id
    return int(s)


def _parse_activity_id(activity_id: str) -> int:
    s = activity_id[4:] if activity_id.startswith("act_") else activity_id
    return int(s)


def activity_post_window_open(activity: Activity, now: datetime | None = None) -> bool:
    """活动开始后至结束 72h 内可发活动态；无 end_at 则从 start 起 72h 内。"""
    now = now or datetime.now(UTC)
    start = to_utc(activity.start_at)
    if activity.end_at:
        end = to_utc(activity.end_at)
        window_start = start
        window_end = end + timedelta(hours=ACTIVITY_POST_HOURS_AFTER_END)
    else:
        window_start = start
        window_end = start + timedelta(hours=ACTIVITY_POST_HOURS_AFTER_END)
    return window_start <= now <= window_end


async def _blocked_user_ids(db: AsyncSession, viewer_id: int) -> set[int]:
    rows = (
        await db.execute(
            select(UserBlock.blocker_id, UserBlock.blocked_id).where(
                (UserBlock.blocker_id == viewer_id) | (UserBlock.blocked_id == viewer_id)
            )
        )
    ).all()
    out: set[int] = set()
    for a, b in rows:
        if a == viewer_id:
            out.add(b)
        else:
            out.add(a)
    return out


async def _author_payload(db: AsyncSession, user: User) -> dict:
    trust = await build_public_trust_fields(db, user)
    return {
        "userId": _uid_str(user.id),
        "nickname": user.nickname or "用户",
        "avatarUrl": user.avatar_url,
        "trustLevel": trust.get("trustLevel"),
        "photoVerified": trust.get("photoVerified", False),
    }


def _normalize_post_location(
    location_name: str | None,
    lat: float | None,
    lng: float | None,
) -> tuple[str | None, float | None, float | None]:
    name = (location_name or "").strip()[:128] or None
    if lat is None and lng is None:
        return name, None, None
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="位置坐标不完整")
    if not name:
        raise HTTPException(status_code=400, detail="请提供位置名称")
    try:
        la = float(lat)
        ln = float(lng)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="位置坐标无效") from exc
    if not (-90.0 <= la <= 90.0 and -180.0 <= ln <= 180.0):
        raise HTTPException(status_code=400, detail="位置坐标无效")
    return name, la, ln


async def _post_to_item(
    db: AsyncSession,
    post: Post,
    author: User,
    viewer_id: int | None,
    *,
    liked: bool = False,
) -> dict:
    author_dict = await _author_payload(db, author)
    return {
        "postId": f"post_{post.id}",
        "postKind": post.post_kind,
        "cityCode": post.city_code,
        "activityId": f"act_{post.activity_id}" if post.activity_id else None,
        "content": post.content,
        "images": list(post.images or []),
        "locationName": post.location_name,
        "lat": float(post.lat) if post.lat is not None else None,
        "lng": float(post.lng) if post.lng is not None else None,
        "topicTags": list(post.topic_tags or []),
        "likeCount": post.like_count or 0,
        "commentCount": post.comment_count or 0,
        "likedByMe": liked,
        "author": author_dict,
        "createdAt": post.created_at,
    }


async def _validate_images(db: AsyncSession, user_id: int, urls: list[str]) -> list[str]:
    out: list[str] = []
    for raw in urls[:9]:
        u = (raw or "").strip()
        if u:
            out.append(validate_stored_feed_image_url(u, user_id))
    return out


async def _check_daily_limit(db: AsyncSession, user_id: int) -> None:
    since = datetime.now(UTC) - timedelta(days=1)
    cnt = int(
        await db.scalar(
            select(func.count(Post.id)).where(
                Post.user_id == user_id,
                Post.status == "published",
                Post.created_at >= since,
            )
        )
        or 0
    )
    if cnt >= MAX_POSTS_PER_DAY:
        raise HTTPException(status_code=429, detail="今日发布次数已达上限")


async def create_post(
    db: AsyncSession,
    user: User,
    *,
    content: str,
    images: list[str],
    city_code: str,
    post_kind: str,
    activity_id: int | None = None,
    location_name: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    topic_tags: list[str] | None = None,
    visibility: str = "city_public",
) -> Post:
    text = (content or "").strip()
    if not text and not images:
        raise HTTPException(status_code=400, detail="内容不能为空")
    if len(text) > MAX_CONTENT_LEN:
        raise HTTPException(status_code=400, detail="内容过长")
    strict = post_kind == POST_KIND_CITY
    blocked = local_text_blocked_reason(text, strict=strict)
    if blocked:
        raise HTTPException(status_code=400, detail=blocked)

    await assert_text_content_safe(user, text, scene=SCENE_SOCIAL, strict=strict)
    if location_name:
        await assert_text_content_safe(
            user, location_name, scene=SCENE_SOCIAL, contact_check=False, strict=strict
        )

    loc_name, loc_lat, loc_lng = _normalize_post_location(location_name, lat, lng)
    tags = [t for t in (topic_tags or []) if t in ALLOWED_TOPICS][:3]
    imgs = await _validate_images(db, user.id, images)
    if imgs:
        await assert_image_urls_safe(user, imgs, scene=SCENE_SOCIAL)
    await _check_daily_limit(db, user.id)

    row = Post(
        user_id=user.id,
        post_kind=post_kind,
        city_code=city_code,
        activity_id=activity_id,
        content=text or "（图片）",
        images=imgs or None,
        location_name=loc_name,
        lat=loc_lat,
        lng=loc_lng,
        topic_tags=tags or None,
        visibility=visibility,
        status="published",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def create_activity_post(
    db: AsyncSession,
    user: User,
    activity_id: int,
    content: str,
    images: list[str],
    *,
    location_name: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> Post:
    activity = await db.scalar(select(Activity).where(Activity.id == activity_id))
    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在")
    if is_city_hall_activity(activity):
        raise HTTPException(status_code=400, detail="城市大群不支持活动态")
    en = await db.scalar(
        select(ActivityEnrollment.id).where(
            ActivityEnrollment.activity_id == activity_id,
            ActivityEnrollment.user_id == user.id,
            ActivityEnrollment.status == "joined",
        )
    )
    if not en:
        raise HTTPException(status_code=403, detail="仅活动参与者可发布")
    now = datetime.now(UTC)
    if effective_activity_status(activity, now) == "cancelled":
        raise HTTPException(status_code=400, detail="活动已取消")
    if not activity_post_window_open(activity, now):
        raise HTTPException(status_code=400, detail="当前不在活动态发布时间窗口内")

    return await create_post(
        db,
        user,
        content=content,
        images=images,
        city_code=activity.city_code,
        post_kind=POST_KIND_ACTIVITY,
        activity_id=activity_id,
        location_name=location_name,
        lat=lat,
        lng=lng,
        topic_tags=["activity_recap"],
    )


async def list_activity_posts(
    db: AsyncSession,
    activity_id: int,
    viewer_id: int | None,
    *,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    filters = [
        Post.activity_id == activity_id,
        Post.post_kind == POST_KIND_ACTIVITY,
        Post.status == "published",
    ]
    total = int(await db.scalar(select(func.count(Post.id)).where(*filters)) or 0)
    rows = (
        await db.execute(
            select(Post, User)
            .join(User, User.id == Post.user_id)
            .where(*filters)
            .order_by(Post.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    liked_ids: set[int] = set()
    if viewer_id and rows:
        pids = [p.id for p, _ in rows]
        liked_ids = set(
            (
                await db.execute(
                    select(PostLike.post_id).where(
                        PostLike.user_id == viewer_id,
                        PostLike.post_id.in_(pids),
                    )
                )
            ).scalars().all()
        )
    items = []
    for post, author in rows:
        if author.status != "active":
            continue
        items.append(
            await _post_to_item(
                db, post, author, viewer_id, liked=post.id in liked_ids
            )
        )
    return items, total


async def list_feed(
    db: AsyncSession,
    viewer: User | None,
    *,
    city_code: str | None,
    scope: str,
    topic: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    filters = [Post.status == "published", Post.post_kind == POST_KIND_CITY]
    blocked: set[int] = set()
    viewer_id = viewer.id if viewer else None
    if viewer_id:
        blocked = await _blocked_user_ids(db, viewer_id)

    if scope == "following":
        if not viewer_id:
            raise HTTPException(status_code=401, detail="需要登录")
        followees = (
            await db.execute(
                select(UserFollow.followee_id).where(UserFollow.follower_id == viewer_id)
            )
        ).scalars().all()
        if not followees:
            return [], 0
        filters.append(Post.user_id.in_(list(followees)))
    else:
        if not city_code:
            raise HTTPException(status_code=400, detail="cityCode required")
        filters.append(Post.city_code == city_code)
        filters.append(Post.visibility == "city_public")

    if topic and topic in ALLOWED_TOPICS:
        filters.append(Post.topic_tags.like(f'%"{topic}"%'))

    total = int(await db.scalar(select(func.count(Post.id)).where(*filters)) or 0)
    rows = (
        await db.execute(
            select(Post, User)
            .join(User, User.id == Post.user_id)
            .where(*filters)
            .order_by(Post.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    liked_ids: set[int] = set()
    if viewer_id and rows:
        pids = [p.id for p, _ in rows]
        liked_ids = set(
            (
                await db.execute(
                    select(PostLike.post_id).where(
                        PostLike.user_id == viewer_id,
                        PostLike.post_id.in_(pids),
                    )
                )
            ).scalars().all()
        )

    items = []
    for post, author in rows:
        if author.status != "active" or author.id in blocked:
            continue
        items.append(
            await _post_to_item(
                db, post, author, viewer_id, liked=post.id in liked_ids
            )
        )
    return items, total


async def get_post_detail(
    db: AsyncSession, post_id: int, viewer_id: int | None
) -> dict:
    row = (
        await db.execute(
            select(Post, User).join(User, User.id == Post.user_id).where(Post.id == post_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="动态不存在")
    post, author = row
    if post.status != "published" or author.status != "active":
        raise HTTPException(status_code=404, detail="动态不存在")
    liked = False
    if viewer_id:
        liked = bool(
            await db.scalar(
                select(PostLike.id).where(
                    PostLike.post_id == post_id, PostLike.user_id == viewer_id
                )
            )
        )
    return await _post_to_item(db, post, author, viewer_id, liked=liked)


async def delete_my_post(db: AsyncSession, user_id: int, post_id: int) -> None:
    post = await db.scalar(select(Post).where(Post.id == post_id))
    if not post or post.user_id != user_id:
        raise HTTPException(status_code=404, detail="动态不存在")
    post.status = "deleted"
    await db.commit()


async def toggle_like(
    db: AsyncSession, user_id: int, post_id: int
) -> tuple[bool, int]:
    post = await db.scalar(select(Post).where(Post.id == post_id, Post.status == "published"))
    if not post:
        raise HTTPException(status_code=404, detail="动态不存在")
    existing = await db.scalar(
        select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == user_id)
    )
    if existing:
        await db.delete(existing)
        post.like_count = max(0, (post.like_count or 0) - 1)
        liked = False
    else:
        db.add(PostLike(post_id=post_id, user_id=user_id))
        post.like_count = (post.like_count or 0) + 1
        liked = True
    await db.commit()
    await db.refresh(post)
    return liked, post.like_count or 0


async def add_comment(
    db: AsyncSession, user: User, post_id: int, content: str
) -> PostComment:
    text = (content or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="评论不能为空")
    if len(text) > MAX_COMMENT_LEN:
        raise HTTPException(status_code=400, detail="评论过长")
    post = await db.scalar(select(Post).where(Post.id == post_id, Post.status == "published"))
    if not post:
        raise HTTPException(status_code=404, detail="动态不存在")
    strict = post.post_kind == POST_KIND_CITY
    blocked = local_text_blocked_reason(text, strict=strict)
    if blocked:
        raise HTTPException(status_code=400, detail=blocked)
    await assert_text_content_safe(user, text, scene=SCENE_COMMENT, strict=strict)

    author = await db.scalar(select(User).where(User.id == post.user_id))
    if author and await either_blocked(db, user.id, author.id):
        raise HTTPException(status_code=403, detail="blocked")

    row = PostComment(post_id=post_id, user_id=user.id, content=text)
    db.add(row)
    post.comment_count = (post.comment_count or 0) + 1
    await db.commit()
    await db.refresh(row)
    return row


async def list_comments(
    db: AsyncSession, post_id: int, *, page: int, page_size: int
) -> tuple[list[dict], int]:
    post = await db.scalar(select(Post.id).where(Post.id == post_id, Post.status == "published"))
    if not post:
        raise HTTPException(status_code=404, detail="动态不存在")
    total = int(
        await db.scalar(
            select(func.count(PostComment.id)).where(PostComment.post_id == post_id)
        )
        or 0
    )
    rows = (
        await db.execute(
            select(PostComment, User)
            .join(User, User.id == PostComment.user_id)
            .where(PostComment.post_id == post_id)
            .order_by(PostComment.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = []
    for c, u in rows:
        if u.status != "active":
            continue
        items.append(
            {
                "commentId": f"pcom_{c.id}",
                "content": c.content,
                "author": await _author_payload(db, u),
                "createdAt": c.created_at,
            }
        )
    return items, total


async def list_user_posts(
    db: AsyncSession,
    target_user_id: int,
    viewer_id: int | None,
    *,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    filters = [
        Post.user_id == target_user_id,
        Post.status == "published",
    ]
    total = int(await db.scalar(select(func.count(Post.id)).where(*filters)) or 0)
    rows = (
        await db.execute(
            select(Post, User)
            .join(User, User.id == Post.user_id)
            .where(*filters)
            .order_by(Post.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    liked_ids: set[int] = set()
    if viewer_id and rows:
        pids = [p.id for p, _ in rows]
        liked_ids = set(
            (
                await db.execute(
                    select(PostLike.post_id).where(
                        PostLike.user_id == viewer_id,
                        PostLike.post_id.in_(pids),
                    )
                )
            ).scalars().all()
        )
    target = await db.scalar(select(User).where(User.id == target_user_id))
    if not target or target.status != "active":
        return [], 0
    items = []
    for post, author in rows:
        items.append(
            await _post_to_item(
                db, post, author, viewer_id, liked=post.id in liked_ids
            )
        )
    return items, total


async def set_follow(
    db: AsyncSession, follower_id: int, followee_id: int, *, follow: bool
) -> bool:
    if follower_id == followee_id:
        raise HTTPException(status_code=400, detail="不能关注自己")
    target = await db.scalar(select(User).where(User.id == followee_id))
    if not target or target.status != "active":
        raise HTTPException(status_code=404, detail="用户不存在")
    if await either_blocked(db, follower_id, followee_id):
        raise HTTPException(status_code=403, detail="blocked")

    row = await db.scalar(
        select(UserFollow).where(
            UserFollow.follower_id == follower_id,
            UserFollow.followee_id == followee_id,
        )
    )
    if follow:
        if not row:
            db.add(UserFollow(follower_id=follower_id, followee_id=followee_id))
        await db.commit()
        return True
    if row:
        await db.delete(row)
    await db.commit()
    return False


async def is_following(db: AsyncSession, follower_id: int, followee_id: int) -> bool:
    return bool(
        await db.scalar(
            select(UserFollow.id).where(
                UserFollow.follower_id == follower_id,
                UserFollow.followee_id == followee_id,
            )
        )
    )
