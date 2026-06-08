"""文本扫描归一化：联系方式过滤、敏感词过滤共用。"""

from __future__ import annotations

import re
import unicodedata

_FULLWIDTH_ZERO = ord("\uff10")
_ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\ufeff", "\u2060")
_COMPACT_STRIP_RE = re.compile(r"[\s\u00b7\u2022\-_*\.\u3000]+")


def normalize_text_for_scan(text: str | None) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    for z in _ZERO_WIDTH:
        t = t.replace(z, "")
    out: list[str] = []
    for ch in t:
        if "\uff10" <= ch <= "\uff19":
            out.append(chr(ord(ch) - _FULLWIDTH_ZERO))
        else:
            out.append(ch)
    return "".join(out)


def compact_text_for_sensitive_scan(text: str | None) -> str:
    """去除空白与常见分隔符，便于命中插空格/符号变体。"""
    norm = normalize_text_for_scan(text).lower()
    return _COMPACT_STRIP_RE.sub("", norm)
