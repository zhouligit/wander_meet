"""同城动态 API：V0.5 活动态 / V1 广场 / V2 关注与话题。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.feed import (
    FeedCommentCreateData,
    FeedCommentCreateRequest,
    FeedCommentListData,
    FeedCommentItem,
    FeedImageUploadData,
    FeedLikeData,
    FeedListData,
    FeedPostCreateData,
    FeedPostCreateRequest,
    FeedPostDetailData,
    FeedPostItem,
    FeedTopicsMetaData,
    UserFollowData,
)
from app.services.bos_storage import BosNotConfiguredError, put_feed_image_bytes
from app.services.feed import (
    ALLOWED_TOPICS,
    POST_KIND_CITY,
    TOPIC_META,
    _parse_post_id,
    _parse_uid,
    add_comment,
    create_post,
    delete_my_post,
    get_post_detail,
    is_following,
    list_comments,
    list_feed,
    list_user_posts,
    set_follow,
    toggle_like,
)
from app.services.city_hall import normalize_city_code

router = APIRouter(tags=["feed"])


@router.get("/feed/topics")
async def feed_topics_meta() -> APIResponse[FeedTopicsMetaData]:
    return APIResponse(data=FeedTopicsMetaData(topics=TOPIC_META))


@router.get("/feed")
async def get_city_feed(
    cityCode: str | None = Query(None),
    scope: str = Query("city", description="city | following"),
    topic: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    viewer: User | None = Depends(get_optional_user),
) -> APIResponse[FeedListData]:
    cc = None
    if cityCode:
        try:
            cc = normalize_city_code(cityCode)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid cityCode") from exc
    if topic and topic not in ALLOWED_TOPICS:
        raise HTTPException(status_code=400, detail="invalid topic")
    items, total = await list_feed(
        db, viewer, city_code=cc, scope=scope, topic=topic, page=page, page_size=pageSize
    )
    return APIResponse(
        data=FeedListData(
            list=[FeedPostItem(**x) for x in items],
            total=total,
            page=page,
            pageSize=pageSize,
        )
    )


@router.post("/feed/posts")
async def create_city_feed_post(
    payload: FeedPostCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[FeedPostCreateData]:
    if (payload.postKind or POST_KIND_CITY) != POST_KIND_CITY:
        raise HTTPException(status_code=400, detail="请使用活动接口发布活动态")
    if not payload.cityCode:
        raise HTTPException(status_code=400, detail="cityCode required")
    try:
        cc = normalize_city_code(payload.cityCode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid cityCode") from exc
    row = await create_post(
        db,
        current_user,
        content=payload.content,
        images=payload.images,
        city_code=cc,
        post_kind=POST_KIND_CITY,
        location_name=payload.locationName,
        topic_tags=payload.topicTags,
        visibility=payload.visibility or "city_public",
    )
    return APIResponse(data=FeedPostCreateData(postId=f"post_{row.id}"))


@router.get("/feed/posts/{post_id}")
async def get_feed_post_detail(
    post_id: str,
    db: AsyncSession = Depends(get_db_session),
    viewer: User | None = Depends(get_optional_user),
) -> APIResponse[FeedPostDetailData]:
    pid = _parse_post_id(post_id)
    data = await get_post_detail(db, pid, viewer.id if viewer else None)
    return APIResponse(data=FeedPostDetailData(**data))


@router.delete("/me/feed/posts/{post_id}")
async def delete_feed_post(
    post_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    await delete_my_post(db, current_user.id, _parse_post_id(post_id))
    return APIResponse(data={"ok": True})


@router.post("/feed/posts/{post_id}/like")
async def like_feed_post(
    post_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[FeedLikeData]:
    liked, count = await toggle_like(db, current_user.id, _parse_post_id(post_id))
    return APIResponse(
        data=FeedLikeData(postId=post_id, liked=liked, likeCount=count)
    )


@router.get("/feed/posts/{post_id}/comments")
async def list_feed_post_comments(
    post_id: str,
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    _: User | None = Depends(get_optional_user),
) -> APIResponse[FeedCommentListData]:
    items, total = await list_comments(
        db, _parse_post_id(post_id), page=page, page_size=pageSize
    )
    return APIResponse(
        data=FeedCommentListData(
            list=[FeedCommentItem(**x) for x in items],
            total=total,
            page=page,
            pageSize=pageSize,
        )
    )


@router.post("/feed/posts/{post_id}/comments")
async def create_feed_post_comment(
    post_id: str,
    payload: FeedCommentCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[FeedCommentCreateData]:
    row = await add_comment(db, current_user, _parse_post_id(post_id), payload.content)
    return APIResponse(data=FeedCommentCreateData(commentId=f"pcom_{row.id}"))


@router.post("/me/feed/images")
async def upload_feed_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> APIResponse[FeedImageUploadData]:
    body = await file.read()
    file_ext = None
    if file.filename and "." in file.filename:
        file_ext = file.filename.rsplit(".", 1)[-1]
    try:
        public_url = await asyncio.to_thread(
            put_feed_image_bytes,
            user_id=current_user.id,
            data=body,
            content_type=file.content_type or "image/jpeg",
            file_ext=file_ext,
        )
    except BosNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return APIResponse(data=FeedImageUploadData(imageUrl=public_url))


@router.get("/users/{user_id}/posts")
async def get_user_feed_posts(
    user_id: str,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    viewer: User | None = Depends(get_optional_user),
) -> APIResponse[FeedListData]:
    uid = _parse_uid(user_id)
    items, total = await list_user_posts(
        db, uid, viewer.id if viewer else None, page=page, page_size=pageSize
    )
    return APIResponse(
        data=FeedListData(
            list=[FeedPostItem(**x) for x in items],
            total=total,
            page=page,
            pageSize=pageSize,
        )
    )


@router.post("/users/{user_id}/follow")
async def follow_user(
    user_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[UserFollowData]:
    following = await set_follow(
        db, current_user.id, _parse_uid(user_id), follow=True
    )
    return APIResponse(data=UserFollowData(userId=user_id, following=following))


@router.delete("/users/{user_id}/follow")
async def unfollow_user(
    user_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[UserFollowData]:
    following = await set_follow(
        db, current_user.id, _parse_uid(user_id), follow=False
    )
    return APIResponse(data=UserFollowData(userId=user_id, following=following))


@router.get("/users/{user_id}/follow")
async def get_follow_status(
    user_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[UserFollowData]:
    following = await is_following(db, current_user.id, _parse_uid(user_id))
    return APIResponse(data=UserFollowData(userId=user_id, following=following))
