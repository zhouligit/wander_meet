"""地点搜索建议：基于城市大群静态目录打平，无需登录。"""

from __future__ import annotations

import unicodedata

from app.services.china_province_meta import province_display_name
from app.services.city_hall_region_catalog import load_static_prefecture_blocks


def _normalize_place_query(raw: str) -> str:
    s = unicodedata.normalize("NFKC", (raw or "").strip()).lower()
    return s.replace("\u3000", " ").strip()


def _place_search_needles(query: str) -> list[str]:
    """支持「枣庄市中区」等：在含「市/州/盟/地区」时增加截到该后缀的别名，便于命中目录里的「枣庄市」。"""
    q = _normalize_place_query(query)
    if not q or len(q) > 32:
        return []
    needles = [q]
    for sep in ("市", "自治州", "盟", "地区", "州"):
        if sep in q:
            sub = q[: q.index(sep) + len(sep)]
            if sub and sub != q:
                needles.append(sub)
    seen: set[str] = set()
    out: list[str] = []
    for n in needles:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def search_place_suggestions(query: str, *, limit: int = 30) -> list[dict]:
    q = _normalize_place_query(query)
    if not q or len(q) > 32:
        return []
    needles = _place_search_needles(q)
    lim = max(1, min(limit, 50))
    out: list[dict] = []
    for blk in load_static_prefecture_blocks():
        pcode = blk["provinceCode"]
        pname = province_display_name(pcode)
        for c in blk["cities"]:
            code = c["cityCode"]
            name = c["cityName"]
            hay = f"{name} {code} {pname}".lower()
            if any(n in hay for n in needles) or any(n in code.lower() for n in needles):
                out.append(
                    {
                        "cityCode": code,
                        "cityName": name,
                        "provinceCode": pcode,
                        "provinceName": pname,
                    }
                )
                if len(out) >= lim:
                    return out
    return out
