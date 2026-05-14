#!/usr/bin/env python3
"""从 modood/Administrative-divisions-of-China 的 cities.json 生成 ``city_hall_prefectures.json``。

用法（需联网）::

  python3 scripts/gen_city_hall_prefectures.py

输出：``app/data/city_hall_prefectures.json``
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_URL = (
    "https://raw.githubusercontent.com/modood/Administrative-divisions-of-China/master/dist/cities.json"
)
OUT = ROOT / "app/data" / "city_hall_prefectures.json"


def main() -> None:
    with urllib.request.urlopen(RAW_URL, timeout=120) as r:
        rows: list[dict] = json.loads(r.read().decode("utf-8"))

    def prov2_to_six(pc: str) -> str:
        return f"{pc.zfill(2)}0000"

    MUNI = {"11", "12", "31", "50"}
    by_p: dict[str, list[dict]] = {}
    for row in rows:
        by_p.setdefault(row["provinceCode"], []).append(row)

    blocks: list[dict] = []
    for pc2 in sorted(by_p.keys(), key=lambda x: int(x)):
        pr_six = prov2_to_six(pc2)
        cities_out: list[dict] = []
        seen: set[str] = set()
        group = sorted(by_p[pc2], key=lambda x: x["code"])
        if pc2 in MUNI and len(group) == 1 and group[0]["name"] == "市辖区":
            name_map = {
                "110000": "北京市",
                "120000": "天津市",
                "310000": "上海市",
                "500000": "重庆市",
            }
            cities_out.append({"cityCode": pr_six, "cityName": name_map[pr_six]})
            seen.add(pr_six)
        else:
            for r in group:
                nm = r["name"]
                ccode = r["code"]
                if nm == "省直辖县级行政区划":
                    continue
                if nm == "市辖区" and pc2 in MUNI:
                    cc = pr_six
                    name_map = {
                        "110000": "北京市",
                        "120000": "天津市",
                        "310000": "上海市",
                        "500000": "重庆市",
                    }
                    nm = name_map[cc]
                elif nm == "市辖区":
                    continue
                else:
                    cc = f"{ccode}00" if len(ccode) == 4 else ccode
                if len(cc) != 6 or not cc.isdigit():
                    continue
                if cc in seen:
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
    n_city = sum(len(b["cities"]) for b in blocks)
    print(f"wrote {OUT} provinces={len(blocks)} cities={n_city}")


if __name__ == "__main__":
    main()
