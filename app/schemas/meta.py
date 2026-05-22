from pydantic import BaseModel


class CategoryItem(BaseModel):
    categoryId: str
    name: str
    icon: str | None = None


class CategoryData(BaseModel):
    categories: list[CategoryItem]


class MetaLabelItem(BaseModel):
    id: str
    label: str


class TravelerRoleMeta(BaseModel):
    id: str
    label: str
    description: str = ""


class InterestTagMeta(BaseModel):
    id: str
    label: str


class InterestCategoryMeta(BaseModel):
    categoryId: str
    name: str
    tags: list[InterestTagMeta]


class PublishMetaData(BaseModel):
    """发布页：是否先付费再发活动（由 ``PAY_PUBLISH_ENABLED`` 控制）。"""

    publishPayEnabled: bool = False
    publishFeeYuan: str = "0.10"


class StayKindMeta(BaseModel):
    id: str
    label: str


class OnboardingMetaData(BaseModel):
    #: ``true`` 时登录后进入多步 ``onboarding`` 页；``false`` 时仅极简昵称+性别
    fullOnboardingEnabled: bool = False
    acquisitionSources: list[MetaLabelItem]
    countryCodes: list[MetaLabelItem]
    travelerRoles: list[TravelerRoleMeta]
    interestCategories: list[InterestCategoryMeta]
    stayKinds: list[StayKindMeta]
