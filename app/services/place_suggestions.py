"""地点搜索建议：基于城市大群静态目录打平，无需登录。"""

from __future__ import annotations

from app.services.china_province_meta import province_display_name
from app.services.city_hall_region_catalog import load_static_prefecture_blocks


def search_place_suggestions(query: str, *, limit: int = 30) -> list[dict]:
    q = (query or "").strip().lower()
    if not q or len(q) > 32:
        return []
    lim = max(1, min(limit, 50))
    out: list[dict] = []
    for blk in load_static_prefecture_blocks():
        pcode = blk["provinceCode"]
        pname = province_display_name(pcode)
        for c in blk["cities"]:
            code = c["cityCode"]
            name = c["cityName"]
            hay = f"{name} {code} {pname}".lower()
            if q in hay or q in code.lower():
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
