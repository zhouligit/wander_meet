"""活动一级 / 二级分类（发现频道、发布页）。"""

from __future__ import annotations

import re

from fastapi import HTTPException

from app.schemas.meta import CategoryItem, SubCategoryItem

CATEGORY_OTHER = "other"

# 一级 + 二级；与 GET /meta/activity-categories 一致
ACTIVITY_CATEGORIES: list[CategoryItem] = [
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
        ],
    ),
    CategoryItem(
        categoryId="games",
        name="游戏娱乐",
        subcategories=[
            SubCategoryItem(subCategoryId="boardgame", name="桌游"),
            SubCategoryItem(subCategoryId="escape_room", name="密室"),
            SubCategoryItem(subCategoryId="esports", name="电竞"),
            SubCategoryItem(subCategoryId="mahjong", name="棋牌"),
        ],
    ),
    CategoryItem(
        categoryId="outdoor",
        name="户外自然",
        subcategories=[
            SubCategoryItem(subCategoryId="hiking", name="徒步"),
            SubCategoryItem(subCategoryId="camping", name="露营"),
            SubCategoryItem(subCategoryId="cycling", name="骑行"),
            SubCategoryItem(subCategoryId="climbing", name="攀岩"),
        ],
    ),
    CategoryItem(
        categoryId="dining",
        name="吃喝探店",
        subcategories=[
            SubCategoryItem(subCategoryId="meal", name="约饭"),
            SubCategoryItem(subCategoryId="bar", name="小酌"),
            SubCategoryItem(subCategoryId="explore_food", name="探店"),
            SubCategoryItem(subCategoryId="afternoon_tea", name="下午茶"),
        ],
    ),
    CategoryItem(
        categoryId="culture",
        name="文娱体验",
        subcategories=[
            SubCategoryItem(subCategoryId="exhibit", name="展览"),
            SubCategoryItem(subCategoryId="show", name="演出"),
            SubCategoryItem(subCategoryId="movie", name="电影"),
            SubCategoryItem(subCategoryId="live", name="Live"),
            SubCategoryItem(subCategoryId="sport_watch", name="观赛"),
        ],
    ),
    CategoryItem(
        categoryId="social",
        name="轻社交",
        subcategories=[
            SubCategoryItem(subCategoryId="coffee", name="咖啡"),
            SubCategoryItem(subCategoryId="tea_chat", name="茶叙"),
            SubCategoryItem(subCategoryId="icebreak", name="破冰"),
            SubCategoryItem(subCategoryId="chat", name="随便聊聊"),
        ],
    ),
    CategoryItem(
        categoryId="cowork",
        name="学习共创",
        subcategories=[
            SubCategoryItem(subCategoryId="language", name="语言"),
            SubCategoryItem(subCategoryId="coworking", name="联合办公"),
            SubCategoryItem(subCategoryId="side_project", name="副业分享"),
            SubCategoryItem(subCategoryId="talk", name="分享会"),
        ],
    ),
    CategoryItem(
        categoryId="citywalk",
        name="Citywalk·探索",
        subcategories=[
            SubCategoryItem(subCategoryId="walk", name="城市漫步"),
            SubCategoryItem(subCategoryId="photo", name="扫街摄影"),
            SubCategoryItem(subCategoryId="route", name="路线打卡"),
        ],
    ),
    CategoryItem(
        categoryId="travel",
        name="旅行·结伴",
        subcategories=[
            SubCategoryItem(subCategoryId="day_trip", name="短途"),
            SubCategoryItem(subCategoryId="weekend", name="周边游"),
            SubCategoryItem(subCategoryId="multi_day", name="多日游"),
            SubCategoryItem(subCategoryId="carpool", name="拼车结伴"),
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
    "dining": "约饭·探店",
    "photography": "摄影扫街",
    "exhibit": "展览",
    "night_run": "夜跑",
}

_CATEGORY_BY_ID = {c.categoryId: c for c in ACTIVITY_CATEGORIES}
_CATEGORY_IDS = set(_CATEGORY_BY_ID)
_SUB_BY_PAIR: dict[tuple[str, str], str] = {}
for _cat in ACTIVITY_CATEGORIES:
    for _sub in _cat.subcategories or []:
        _SUB_BY_PAIR[(_cat.categoryId, _sub.subCategoryId)] = _sub.name

_ALL_VALID_CATEGORY_IDS = _CATEGORY_IDS | set(_LEGACY_CATEGORY_NAMES)

_THEME_BAD_RE = re.compile(r'[<>"\'\\]')


def primary_category_name(category_id: str) -> str:
    cid = (category_id or "").strip()
    if cid in _CATEGORY_BY_ID:
        return _CATEGORY_BY_ID[cid].name
    return _LEGACY_CATEGORY_NAMES.get(cid, cid or "活动")


def subcategory_name(category_id: str, sub_category_id: str | None) -> str | None:
    sid = (sub_category_id or "").strip()
    if not sid:
        return None
    return _SUB_BY_PAIR.get((category_id, sid), sid)


def category_display_name(
    category_id: str,
    sub_category_id: str | None = None,
    category_label: str | None = None,
) -> str:
    """卡片 / 详情展示：``运动健身 · 篮球``、``其他 · 主题``。"""
    cid = (category_id or "").strip()
    if cid == CATEGORY_OTHER:
        label = (category_label or "").strip()
        return f"其他 · {label}" if label else "其他"
    if cid in _LEGACY_CATEGORY_NAMES and not (sub_category_id or "").strip():
        return _LEGACY_CATEGORY_NAMES[cid]
    l1 = primary_category_name(cid)
    sub = subcategory_name(cid, sub_category_id)
    return f"{l1} · {sub}" if sub else l1


def normalize_activity_category(
    category_id: str,
    sub_category_id: str | None = None,
    category_label: str | None = None,
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

    if label:
        raise HTTPException(status_code=400, detail="仅「其他」分类可填写活动主题")
    if sid and sid not in {s.subCategoryId for s in (_CATEGORY_BY_ID[cid].subcategories or [])}:
        raise HTTPException(status_code=400, detail="无效的二级分类")

    return cid, sid, None
