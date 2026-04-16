from pydantic import BaseModel


class CategoryItem(BaseModel):
    categoryId: str
    name: str
    icon: str | None = None


class CategoryData(BaseModel):
    categories: list[CategoryItem]
