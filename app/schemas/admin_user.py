from pydantic import BaseModel, Field

from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z


class AdminMergeUsersRequest(BaseModel):
    #: 被合并账号（合并后删除），多为纯微信临时号
    fromUserId: str = Field(min_length=1, max_length=32)
    #: 保留的主账号，多为先有手机号的短信账号
    toUserId: str = Field(min_length=1, max_length=32)
    note: str | None = Field(default=None, max_length=500)


class AdminMergeUsersData(BaseModel):
    fromUserId: str
    toUserId: str
    phoneMasked: str
    phoneBound: bool
    mpOpenidTransferred: bool


class AdminUserSearchItem(BaseModel):
    userId: str
    nickname: str
    phoneMasked: str
    phoneBound: bool
    hasMpOpenid: bool
    mpOpenidSuffix: str | None = None
    status: str
    createdAt: str


class AdminUserSearchData(BaseModel):
    list: list[AdminUserSearchItem]


def parse_public_user_id(user_id: str) -> int:
    s = (user_id or "").strip()
    if s.startswith("u_"):
        s = s[2:]
    return int(s)


def build_admin_user_search_item(user) -> AdminUserSearchItem:
    from app.services.user_phone_bind import mask_user_phone, user_has_phone

    openid = (user.mp_openid or "").strip()
    suffix = openid[-6:] if len(openid) >= 6 else (openid or None)
    return AdminUserSearchItem(
        userId=f"u_{user.id}",
        nickname=user.nickname,
        phoneMasked=mask_user_phone(user),
        phoneBound=user_has_phone(user),
        hasMpOpenid=bool(openid),
        mpOpenidSuffix=suffix,
        status=user.status,
        createdAt=datetime_to_rfc3339_utc_z(user.created_at),
    )
