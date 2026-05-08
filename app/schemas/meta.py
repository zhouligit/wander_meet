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


class StayKindMeta(BaseModel):
    id: str
    label: str


class OnboardingMetaData(BaseModel):
    acquisitionSources: list[MetaLabelItem]
    countryCodes: list[MetaLabelItem]
    travelerRoles: list[TravelerRoleMeta]
    interestCategories: list[InterestCategoryMeta]
    stayKinds: list[StayKindMeta]
