from fastapi import APIRouter

from app.schemas.common import APIResponse
from app.schemas.meta import CategoryData, CategoryItem

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/activity-categories")
async def activity_categories() -> APIResponse[CategoryData]:
    categories = [
        CategoryItem(categoryId="coffee", name="咖啡"),
        CategoryItem(categoryId="citywalk", name="Citywalk"),
        CategoryItem(categoryId="hiking", name="徒步"),
        CategoryItem(categoryId="boardgame", name="桌游"),
    ]
    return APIResponse(data=CategoryData(categories=categories))

