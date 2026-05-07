"""中国大陆手机号：仅允许 11 位数字，号段 13–19（不含 12）。支持提交中带空格等，会先抽取数字再校验。"""

from __future__ import annotations

import re

_CN_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")


def normalize_mobile_digits(text: str) -> str:
    return "".join(c for c in (text or "").strip() if c.isdigit())


def parse_cn_mobile(text: str) -> str | None:
    """若为合法大陆手机号则返回归一化后的 11 位字符串，否则 ``None``。"""
    n = normalize_mobile_digits(text)
    if _CN_MOBILE_RE.match(n):
        return n
    return None
