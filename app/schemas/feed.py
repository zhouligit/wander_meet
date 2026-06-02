from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z_shanghai_naive


class FeedAuthor(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str | None = None
    trustLevel: str | None = None
    photoVerified: bool = False


class FeedPostItem(BaseModel):
    postId: str
    postKind: str
    cityCode: str
    activityId: str | None = None
    content: str
    images: list[str] = Field(default_factory=list)
    locationName: str | None = None
    topicTags: list[str] = Field(default_factory=list)
    likeCount: int = 0
    commentCount: int = 0
    likedByMe: bool = False
    author: FeedAuthor
    createdAt: datetime

    @field_serializer("createdAt")
    def _ser_created(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


class FeedListData(BaseModel):
    list: list[FeedPostItem]
    total: int
    page: int
    pageSize: int


class FeedPostCreateRequest(BaseModel):
    content: str
    images: list[str] = Field(default_factory=list, max_length=9)
    cityCode: str | None = None
    activityId: str | None = None
    locationName: str | None = None
    topicTags: list[str] = Field(default_factory=list, max_length=3)
    postKind: str | None = None
    visibility: str | None = None


class FeedPostCreateData(BaseModel):
    postId: str


class FeedPostDetailData(FeedPostItem):
    pass


class FeedLikeData(BaseModel):
    postId: str
    liked: bool
    likeCount: int


class FeedCommentItem(BaseModel):
    commentId: str
    content: str
    author: FeedAuthor
    createdAt: datetime

    @field_serializer("createdAt")
    def _ser_created(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


class FeedCommentListData(BaseModel):
    list: list[FeedCommentItem]
    total: int
    page: int
    pageSize: int


class FeedCommentCreateRequest(BaseModel):
    content: str


class FeedCommentCreateData(BaseModel):
    commentId: str


class FeedImageUploadData(BaseModel):
    imageUrl: str


class UserFollowData(BaseModel):
    userId: str
    following: bool


class FeedTopicsMetaData(BaseModel):
    topics: list[dict[str, str]]
