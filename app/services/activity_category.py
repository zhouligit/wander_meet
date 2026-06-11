"""活动一级 / 二级分类（发现频道、发布页）。"""

from __future__ import annotations

import re

from fastapi import HTTPException

from app.schemas.meta import CategoryItem, SubCategoryItem

CATEGORY_OTHER = "other"

# 一级 + 二级；与 GET /meta/activity-categories 一致（2026-06 类目调整）
ACTIVITY_CATEGORIES: list[CategoryItem] = [
    CategoryItem(
        categoryId="dining",
        name="吃吃喝喝",
        subcategories=[
            SubCategoryItem(subCategoryId="meal", name="约饭"),
            SubCategoryItem(subCategoryId="coffee", name="咖啡"),
            SubCategoryItem(subCategoryId="tea_tasting", name="品茶"),
            SubCategoryItem(subCategoryId="afternoon_tea", name="下午茶"),
            SubCategoryItem(subCategoryId="bar", name="小酌一下"),
        ],
    ),
    CategoryItem(
        categoryId="leisure",
        name="休闲娱乐",
        subcategories=[
            SubCategoryItem(subCategoryId="karaoke", name="K歌"),
            SubCategoryItem(subCategoryId="movie", name="看电影"),
            SubCategoryItem(subCategoryId="escape_room", name="密室"),
            SubCategoryItem(subCategoryId="script_murder", name="剧本杀"),
            SubCategoryItem(subCategoryId="billiards", name="台球"),
            SubCategoryItem(subCategoryId="mahjong", name="棋牌"),
            SubCategoryItem(subCategoryId="arcade", name="电玩"),
            SubCategoryItem(subCategoryId="diy", name="拼豆/DIY"),
            SubCategoryItem(subCategoryId="cat_mouse", name="猫鼠游戏"),
        ],
    ),
    CategoryItem(
        categoryId="shows",
        name="观影演出",
        subcategories=[
            SubCategoryItem(subCategoryId="concert", name="演唱会"),
            SubCategoryItem(subCategoryId="talk_show", name="脱口秀"),
            SubCategoryItem(subCategoryId="esports", name="电竞"),
            SubCategoryItem(subCategoryId="drama", name="话剧"),
            SubCategoryItem(subCategoryId="musical", name="音乐剧"),
            SubCategoryItem(subCategoryId="crosstalk", name="相声"),
        ],
    ),
    CategoryItem(
        categoryId="sports",
        name="运动健身",
        subcategories=[
            SubCategoryItem(subCategoryId="basketball", name="篮球"),
            SubCategoryItem(subCategoryId="badminton", name="羽毛球"),
            SubCategoryItem(subCategoryId="tennis", name="网球"),
            SubCategoryItem(subCategoryId="running", name="跑步"),
            SubCategoryItem(subCategoryId="fitness", name="健身"),
            SubCategoryItem(subCategoryId="frisbee", name="飞盘"),
            SubCategoryItem(subCategoryId="swim", name="游泳"),
            SubCategoryItem(subCategoryId="yoga", name="瑜伽"),
        ],
    ),
    CategoryItem(
        categoryId="outdoor",
        name="户外自然",
        subcategories=[
            SubCategoryItem(subCategoryId="skiing", name="滑雪"),
            SubCategoryItem(subCategoryId="hiking", name="徒步"),
            SubCategoryItem(subCategoryId="picnic", name="野炊"),
            SubCategoryItem(subCategoryId="cycling", name="骑行"),
            SubCategoryItem(subCategoryId="climbing", name="攀岩"),
            SubCategoryItem(subCategoryId="offroad", name="越野"),
            SubCategoryItem(subCategoryId="fishing", name="钓鱼"),
            SubCategoryItem(subCategoryId="picking", name="采摘"),
            SubCategoryItem(subCategoryId="photography", name="摄影"),
        ],
    ),
    CategoryItem(
        categoryId="travel",
        name="旅行结伴",
        subcategories=[
            SubCategoryItem(subCategoryId="summer_escape", name="夏季避暑"),
            SubCategoryItem(subCategoryId="winter_escape", name="冬季避寒"),
            SubCategoryItem(subCategoryId="weekend_trip", name="周边游"),
        ],
    ),
    CategoryItem(
        categoryId="learning",
        name="学习交流",
        subcategories=[
            SubCategoryItem(subCategoryId="book_club", name="读书分享"),
            SubCategoryItem(subCategoryId="talent", name="才艺展示"),
            SubCategoryItem(subCategoryId="professional", name="专业交流"),
            SubCategoryItem(subCategoryId="language_culture", name="语言文化"),
        ],
    ),
    CategoryItem(categoryId=CATEGORY_OTHER, name="其他", subcategories=[]),
]

# 旧版扁平 category_id（历史活动只读展示 / 兼容更新）
_LEGACY_CATEGORY_NAMES: dict[str, str] = {
    "coffee": "咖啡",
    "citywalk": "Citywalk",
    "hiking": "徒步",
    "boardgame": "桌游",
    "coworking": "联合办公·共创",
    "indie": "副业·独立开发",
    "language": "语言交换",
    "photography": "摄影扫街",
    "exhibit": "展览",
    "night_run": "夜跑",
}

# 已下线的一级类目（历史活动 category_id 仍合法，仅展示 / 更新，不可新发）
_RETIRED_L1_NAMES: dict[str, str] = {
    "games": "游戏娱乐",
    "culture": "文娱体验",
    "social": "轻社交",
    "cowork": "学习共创",
    "citywalk": "Citywalk·探索",
}

# 已下线一级下的二级（展示 + 校验历史数据）
_LEGACY_L1_SUBS: dict[str, dict[str, str]] = {
    "games": {
        "boardgame": "桌游",
        "escape_room": "密室",
        "esports": "电竞",
        "mahjong": "棋牌",
    },
    "culture": {
        "exhibit": "展览",
        "show": "演出",
        "movie": "电影",
        "live": "Live",
        "sport_watch": "观赛",
    },
    "social": {
        "coffee": "咖啡",
        "tea_chat": "茶叙",
        "icebreak": "破冰",
        "chat": "随便聊聊",
    },
    "cowork": {
        "language": "语言",
        "coworking": "联合办公",
        "side_project": "副业分享",
        "talk": "分享会",
    },
    "citywalk": {
        "walk": "城市漫步",
        "photo": "扫街摄影",
        "route": "路线打卡",
    },
    "dining": {
        "explore_food": "探店",
        "bar": "小酌",
    },
    "outdoor": {
        "camping": "露营",
    },
    "travel": {
        "day_trip": "短途",
        "weekend": "周边游",
        "multi_day": "多日游",
        "carpool": "拼车结伴",
    },
}

_CATEGORY_BY_ID = {c.categoryId: c for c in ACTIVITY_CATEGORIES}
_CATEGORY_IDS = set(_CATEGORY_BY_ID)
_SUB_BY_PAIR: dict[tuple[str, str], str] = {}
for _cat in ACTIVITY_CATEGORIES:
    for _sub in _cat.subcategories or []:
        _SUB_BY_PAIR[(_cat.categoryId, _sub.subCategoryId)] = _sub.name

_ALL_VALID_CATEGORY_IDS = (
    _CATEGORY_IDS | set(_LEGACY_CATEGORY_NAMES) | set(_RETIRED_L1_NAMES)
)

_THEME_BAD_RE = re.compile(r'[<>"\'\\]')


def primary_category_name(category_id: str) -> str:
    cid = (category_id or "").strip()
    if cid in _CATEGORY_BY_ID:
        return _CATEGORY_BY_ID[cid].name
    if cid in _RETIRED_L1_NAMES:
        return _RETIRED_L1_NAMES[cid]
    return _LEGACY_CATEGORY_NAMES.get(cid, cid or "活动")


def subcategory_name(category_id: str, sub_category_id: str | None) -> str | None:
    sid = (sub_category_id or "").strip()
    if not sid:
        return None
    if (category_id, sid) in _SUB_BY_PAIR:
        return _SUB_BY_PAIR[(category_id, sid)]
    legacy = _LEGACY_L1_SUBS.get(category_id, {})
    return legacy.get(sid, sid)


def category_display_name(
    category_id: str,
    sub_category_id: str | None = None,
    category_label: str | None = None,
) -> str:
    """卡片 / 详情展示：``吃吃喝喝 · 咖啡``、``其他 · 主题``。"""
    cid = (category_id or "").strip()
    if cid == CATEGORY_OTHER:
        label = (category_label or "").strip()
        return f"其他 · {label}" if label else "其他"
    if cid in _LEGACY_CATEGORY_NAMES and not (sub_category_id or "").strip():
        return _LEGACY_CATEGORY_NAMES[cid]
    l1 = primary_category_name(cid)
    sub = subcategory_name(cid, sub_category_id)
    return f"{l1} · {sub}" if sub else l1


def _is_retired_l1(category_id: str) -> bool:
    return category_id in _RETIRED_L1_NAMES


def normalize_activity_category(
    category_id: str,
    sub_category_id: str | None = None,
    category_label: str | None = None,
    *,
    allow_retired: bool = False,
) -> tuple[str, str | None, str | None]:
    """
    校验发布/更新类目。
    返回 ``(category_id, sub_category_id, category_label)``；
    ``category_label`` 仅 ``other`` 时有值。
    """
    cid = (category_id or "").strip()[:32]
    if not cid:
        raise HTTPException(status_code=400, detail="请选择活动分类")
    if cid not in _ALL_VALID_CATEGORY_IDS:
        raise HTTPException(status_code=400, detail="无效的活动分类")

    sid = (sub_category_id or "").strip()[:32] or None
    label = (category_label or "").strip()[:32] or None

    if cid == CATEGORY_OTHER:
        if sid:
            raise HTTPException(status_code=400, detail="「其他」分类不可选二级类目")
        if not label or len(label) < 2:
            raise HTTPException(status_code=400, detail="请填写活动主题（2～16 字）")
        if len(label) > 16:
            raise HTTPException(status_code=400, detail="活动主题不超过 16 字")
        if _THEME_BAD_RE.search(label):
            raise HTTPException(status_code=400, detail="活动主题含非法字符")
        return cid, None, label

    if cid in _LEGACY_CATEGORY_NAMES:
        if sid or label:
            raise HTTPException(status_code=400, detail="旧版分类不可填写二级或主题，请重新选择分类")
        return cid, None, None

    if _is_retired_l1(cid):
        if not allow_retired:
            raise HTTPException(status_code=400, detail="该分类已调整，请重新选择分类")
        if label:
            raise HTTPException(status_code=400, detail="该分类已调整，请重新选择分类")
        allowed = _LEGACY_L1_SUBS.get(cid, {})
        if sid and sid not in allowed:
            raise HTTPException(status_code=400, detail="无效的二级分类")
        return cid, sid, None

    if label:
        raise HTTPException(status_code=400, detail="仅「其他」分类可填写活动主题")
    subs = _CATEGORY_BY_ID[cid].subcategories or []
    if subs and not sid:
        raise HTTPException(status_code=400, detail="请选择二级分类")
    if sid and sid not in {s.subCategoryId for s in subs}:
        # 同 id 一级下历史二级（如 outdoor/camping）仍允许更新旧活动
        legacy = _LEGACY_L1_SUBS.get(cid, {})
        if not sid or sid not in legacy:
            raise HTTPException(status_code=400, detail="无效的二级分类")

    return cid, sid, None
