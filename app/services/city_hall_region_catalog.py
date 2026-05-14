"""静态地级市目录（与已开通城市大群合并为完整「省 → 市」列表）。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data" / "city_hall_prefectures.json"


@lru_cache
def load_static_prefecture_blocks() -> tuple[dict, ...]:
    """每省一项：``provinceCode``（六位省码）、``cities`` 为 ``{cityCode, cityName}`` 列表。"""
    data = json.loads(_DATA.read_text(encoding="utf-8"))
    return tuple(data)
