from fastapi import APIRouter

from app.schemas.common import APIResponse
from app.schemas.city_group import CityGroupsMetaData
from app.schemas.meta import (
    CategoryData,
    CategoryItem,
    InterestCategoryMeta,
    InterestTagMeta,
    MetaLabelItem,
    OnboardingMetaData,
    StayKindMeta,
    TravelerRoleMeta,
)

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/city-groups")
async def city_groups_meta() -> APIResponse[CityGroupsMetaData]:
    """城市大群前端文案与开关（无需登录）。"""
    return APIResponse(
        data=CityGroupsMetaData(
            recommendTip="城市大群由系统在首个用户加入时自动创建，群主为系统管理员；目录按省份分组，省内按展示名/城市编码排序。加入后使用与活动相同的群聊能力。",
            userCanCreate=False,
        )
    )


@router.get("/activity-categories")
async def activity_categories() -> APIResponse[CategoryData]:
    categories = [
        CategoryItem(categoryId="coffee", name="咖啡"),
        CategoryItem(categoryId="citywalk", name="Citywalk"),
        CategoryItem(categoryId="hiking", name="徒步"),
        CategoryItem(categoryId="boardgame", name="桌游"),
        CategoryItem(categoryId="coworking", name="联合办公·共创"),
        CategoryItem(categoryId="indie", name="副业·独立开发"),
        CategoryItem(categoryId="language", name="语言交换"),
        CategoryItem(categoryId="dining", name="约饭·探店"),
        CategoryItem(categoryId="photography", name="摄影扫街"),
    ]
    return APIResponse(data=CategoryData(categories=categories))


@router.get("/onboarding")
async def onboarding_meta() -> APIResponse[OnboardingMetaData]:
    """新手引导可选文案：渠道、旅行身份、兴趣词表、停留类型（无需登录）。"""
    data = OnboardingMetaData(
        acquisitionSources=[
            MetaLabelItem(id="xiaohongshu", label="小红书"),
            MetaLabelItem(id="douyin", label="抖音"),
            MetaLabelItem(id="wechat", label="微信 / 公众号"),
            MetaLabelItem(id="friend", label="朋友推荐"),
            MetaLabelItem(id="search", label="搜索"),
            MetaLabelItem(id="other", label="其他"),
        ],
        countryCodes=[
            MetaLabelItem(id="CN", label="中国"),
            MetaLabelItem(id="US", label="美国"),
            MetaLabelItem(id="JP", label="日本"),
            MetaLabelItem(id="KR", label="韩国"),
            MetaLabelItem(id="GB", label="英国"),
            MetaLabelItem(id="OTHER", label="其他"),
        ],
        travelerRoles=[
            TravelerRoleMeta(id="leisure", label="休闲旅行", description="游玩探索为主"),
            TravelerRoleMeta(id="digital_nomad", label="数字游民", description="边旅行边远程工作"),
            TravelerRoleMeta(id="student_abroad", label="留学", description="在海外学习"),
            TravelerRoleMeta(id="expat", label="外派/长居", description="长期生活在当地"),
            TravelerRoleMeta(id="local_host", label="本地东道主", description="愿意认识新朋友"),
        ],
        interestCategories=[
            InterestCategoryMeta(
                categoryId="food",
                name="美食饮品",
                tags=[
                    InterestTagMeta(id="foodie", label="美食探店"),
                    InterestTagMeta(id="coffee", label="咖啡"),
                    InterestTagMeta(id="tea", label="茶饮"),
                    InterestTagMeta(id="wine", label="小酌"),
                ],
            ),
            InterestCategoryMeta(
                categoryId="nightlife",
                name="夜生活",
                tags=[
                    InterestTagMeta(id="bar", label="清吧"),
                    InterestTagMeta(id="live_music", label="现场音乐"),
                    InterestTagMeta(id="club", label="夜店聚会"),
                ],
            ),
            InterestCategoryMeta(
                categoryId="culture",
                name="文化艺术",
                tags=[
                    InterestTagMeta(id="museum", label="看展"),
                    InterestTagMeta(id="photography", label="摄影"),
                    InterestTagMeta(id="reading", label="阅读"),
                ],
            ),
            InterestCategoryMeta(
                categoryId="outdoor",
                name="户外",
                tags=[
                    InterestTagMeta(id="hiking", label="徒步"),
                    InterestTagMeta(id="cycling", label="骑行"),
                    InterestTagMeta(id="camping", label="露营"),
                ],
            ),
        ],
        stayKinds=[
            StayKindMeta(id="indefinite", label="常住 / 暂无离开计划"),
            StayKindMeta(id="fixed_dates", label="有明确停留区间"),
        ],
    )
    return APIResponse(data=data)

