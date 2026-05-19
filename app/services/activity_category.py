"""活动大类（发现频道）与「其他 + 自定义主题」。"""

from __future__ import annotations

import re

from fastapi import HTTPException

from app.schemas.meta import CategoryItem

CATEGORY_OTHER = "other"

# 正式大类（含「其他」）；与 GET /meta/activity-categories 一致
ACTIVITY_CATEGORIES: list[CategoryItem] = [
    CategoryItem(categoryId="coffee", name="咖啡"),
    CategoryItem(categoryId="citywalk", name="Citywalk"),
    CategoryItem(categoryId="hiking", name="徒步"),
    CategoryItem(categoryId="boardgame", name="桌游"),
    CategoryItem(categoryId="coworking", name="联合办公·共创"),
    CategoryItem(categoryId="indie", name="副业·独立开发"),
    CategoryItem(categoryId="language", name="语言交换"),
    CategoryItem(categoryId="dining", name="约饭·探店"),
    CategoryItem(categoryId="photography", name="摄影扫街"),
    CategoryItem(categoryId=CATEGORY_OTHER, name="其他"),
]

_CATEGORY_IDS = {c.categoryId for c in ACTIVITY_CATEGORIES}
_CATEGORY_NAMES = {c.categoryId: c.name for c in ACTIVITY_CATEGORIES}

_THEME_BAD_RE = re.compile(r'[<>"\'\\]')


def category_display_name(category_id: str, category_label: str | None = None) -> str:
    cid = (category_id or "").strip()
    base = _CATEGORY_NAMES.get(cid, cid or "活动")
    if cid == CATEGORY_OTHER:
        label = (category_label or "").strip()
        return f"其他 · {label}" if label else "其他"
    return base


def normalize_activity_category(
    category_id: str,
    category_label: str | None,
) -> tuple[str, str | None]:
    """
    校验并规范化发布/更新时的类目。
    返回 (category_id, category_label)；非 other 时 label 为 None。
    """
    cid = (category_id or "").strip()[:32]
    if not cid:
        raise HTTPException(status_code=400, detail="请选择活动分类")
    if cid not in _CATEGORY_IDS:
        raise HTTPException(status_code=400, detail="无效的活动分类")

    label = (category_label or "").strip()[:32]
    if cid == CATEGORY_OTHER:
        if len(label) < 2:
            raise HTTPException(status_code=400, detail="请填写活动主题（2～16 字）")
        if len(label) > 16:
            raise HTTPException(status_code=400, detail="活动主题不超过 16 字")
        if _THEME_BAD_RE.search(label):
            raise HTTPException(status_code=400, detail="活动主题含非法字符")
        return cid, label

    if label:
        raise HTTPException(status_code=400, detail="仅「其他」分类可填写活动主题")
    return cid, None
