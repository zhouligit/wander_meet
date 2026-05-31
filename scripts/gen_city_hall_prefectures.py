#!/usr/bin/env python3
"""生成 ``app/data/city_hall_prefectures.json``。

- 普通省：地级市（``cities.json``，建议经 jsDelivr 拉取 modood 数据）。
- 直辖市（京/沪/津/渝）：全市一条（``110000`` 等）+ 区县列表，来自 ``city_hall_municipality_districts.json``。
- 其他省：逻辑不变，仍为地级市列表。

用法::

  python3 scripts/gen_city_hall_prefectures.py
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CITIES_URL = (
    "https://cdn.jsdelivr.net/gh/modood/Administrative-divisions-of-China@master/dist/cities.json"
)
MUNI_PATH = ROOT / "app/data/city_hall_municipality_districts.json"
OUT = ROOT / "app/data/city_hall_prefectures.json"

MUNI_2 = {"11", "12", "31", "50"}
# 直辖市省级码（六位）与展示名；目录首条为「全市」大群，其后为区县。
MUNI_CITY: dict[str, tuple[str, str]] = {
    "11": ("110000", "北京市"),
    "12": ("120000", "天津市"),
    "31": ("310000", "上海市"),
    "50": ("500000", "重庆市"),
}


def _municipality_cities(pc2: str, districts: list[dict]) -> list[dict]:
    """京/沪/津/渝：全市 + 区县；去重避免区县文件里误含市级码。"""
    city_code, city_name = MUNI_CITY[pc2]
    rest = [d for d in districts if d.get("cityCode") != city_code]
    return [{"cityCode": city_code, "cityName": city_name}, *rest]


def prov2_to_six(pc: str) -> str:
    return f"{pc.zfill(2)}0000"


def main() -> None:
    with urllib.request.urlopen(CITIES_URL, timeout=120) as r:
        rows: list[dict] = json.loads(r.read().decode("utf-8"))
    muni: dict[str, list[dict]] = json.loads(MUNI_PATH.read_text(encoding="utf-8"))

    by_p: dict[str, list[dict]] = {}
    for row in rows:
        by_p.setdefault(row["provinceCode"], []).append(row)

    blocks: list[dict] = []
    for pc2 in sorted(by_p.keys(), key=lambda x: int(x)):
        pr_six = prov2_to_six(pc2)
        if pc2 in MUNI_2:
            districts = list(muni.get(pc2) or [])
            if districts:
                cities_out = _municipality_cities(pc2, districts)
            else:
                cc, nm = MUNI_CITY[pc2]
                cities_out = [{"cityCode": cc, "cityName": nm}]
        else:
            cities_out = []
            seen: set[str] = set()
            for row in sorted(by_p[pc2], key=lambda x: x["code"]):
                nm, ccode = row["name"], row["code"]
                if nm in ("省直辖县级行政区划", "市辖区"):
                    continue
                cc = f"{ccode}00" if len(ccode) == 4 else ccode
                if len(cc) != 6 or not cc.isdigit() or cc in seen:
                    continue
                seen.add(cc)
                cities_out.append({"cityCode": cc, "cityName": nm})
            cities_out.sort(key=lambda x: x["cityCode"])

        blocks.append({"provinceCode": pr_six, "cities": cities_out})

    extra = [
        ("710000", "710000", "台湾省"),
        ("810000", "810000", "香港特别行政区"),
        ("820000", "820000", "澳门特别行政区"),
    ]
    existing_p = {b["provinceCode"] for b in blocks}
    for pr_six, cc, nm in extra:
        if pr_six not in existing_p:
            blocks.append({"provinceCode": pr_six, "cities": [{"cityCode": cc, "cityName": nm}]})
            existing_p.add(pr_six)

    blocks.sort(key=lambda b: b["provinceCode"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(blocks, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n_leaf = sum(len(b["cities"]) for b in blocks)
    print(f"wrote {OUT} provinces={len(blocks)} leaf-locations={n_leaf}")


if __name__ == "__main__":
    main()
