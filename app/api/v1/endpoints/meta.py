from fastapi import APIRouter, Query, Response

from app.core.config import get_settings
from app.schemas.city_group import CityGroupsMetaData
from app.schemas.common import APIResponse
from app.schemas.meta import CategoryData, OnboardingMetaData
from app.schemas.place_activity import PlaceSuggestionItem, PlaceSuggestionsData
from app.services.meta_cache import (
    get_cached_activity_categories,
    get_cached_city_groups_meta,
    get_cached_onboarding_meta,
)
from app.services.place_suggestions import search_place_suggestions

router = APIRouter(prefix="/meta", tags=["meta"])


def _apply_meta_http_cache(response: Response) -> None:
    max_age = get_settings().meta_http_cache_max_age_seconds
    if max_age > 0:
        response.headers["Cache-Control"] = f"public, max-age={max_age}"


@router.get("/city-groups")
async def city_groups_meta(response: Response) -> APIResponse[CityGroupsMetaData]:
    """城市大群前端开关（无需登录）。建群规则不向端上暴露。"""
    _apply_meta_http_cache(response)
    return APIResponse(data=get_cached_city_groups_meta())


@router.get("/activity-categories")
async def activity_categories(response: Response) -> APIResponse[CategoryData]:
    _apply_meta_http_cache(response)
    return APIResponse(data=get_cached_activity_categories())


@router.get("/onboarding")
async def onboarding_meta(response: Response) -> APIResponse[OnboardingMetaData]:
    """新手引导可选文案：渠道、旅行身份、兴趣词表、停留类型（无需登录）。"""
    _apply_meta_http_cache(response)
    return APIResponse(data=get_cached_onboarding_meta())


@router.get("/place-suggestions")
async def place_suggestions(
    q: str = Query("", max_length=32),
) -> APIResponse[PlaceSuggestionsData]:
    """按关键字匹配城市/区县名或编码（与活动 ``city_code`` 体系一致）。"""
    rows = search_place_suggestions(q, limit=30)
    return APIResponse(
        data=PlaceSuggestionsData(
            list=[PlaceSuggestionItem(**r) for r in rows],
        )
    )
