"""本地敏感词过滤（涉政人物/高风险词，P0 fail-closed）。"""

from __future__ import annotations

import re

from app.services.text_scan_utils import compact_text_for_sensitive_scan, normalize_text_for_scan

# 与微信内容安全统一的用户提示
SENSITIVE_REJECT_DETAIL = "所发布内容含违规信息，请修改后重试"

# 全场景拦截：涉政人物姓名/常见称谓、高风险涉政词
_CORE_TERMS: tuple[str, ...] = (
    # 现任 / 近期主要领导人（全名与常见简称）
    "习近平",
    "习主席",
    "习大大",
    "习书记",
    "习总",
    "李克强",
    "毛泽东",
    "毛主席",
    "邓小平",
    "江泽民",
    "胡锦涛",
    "温家宝",
    "朱镕基",
    "周恩来",
    "华国锋",
    # 高风险涉政 / 违法组织相关
    "六四",
    "六四事件",
    "8964",
    "64事件",
    "天安门事件",
    "天安门屠杀",
    "法轮功",
    "法轮大法",
    "真善忍",
    "台独",
    "台湾独立",
    "港独",
    "藏独",
    "疆独",
    "分裂国家",
    "颠覆政权",
    "反共产党",
    "反党",
    "反共",
    "颜色革命",
)

# 城市大群 / 城主公告等加严：网络隐喻、谐音与额外别名
_STRICT_EXTRA_TERMS: tuple[str, ...] = (
    "习近乎",
    "习维尼",
    "维尼",
    "庆丰",
    "包子",
    "刁大大",
    "膜蛤",
    "赵家人",
    "扛麦郎",
    "xijinping",
    "xi jinping",
)

_STRICT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"习\s*近\s*平"),
    re.compile(r"(?i)x\s*i\s*j\s*i\s*n\s*p\s*i\s*n\s*g"),
    re.compile(r"总理\s*李强|李强\s*总理|国务院总理"),
)


def _contains_term(compact: str, term: str) -> bool:
    needle = compact_text_for_sensitive_scan(term)
    if not needle:
        return False
    return needle in compact


def sensitive_text_blocked_reason(text: str | None, *, strict: bool = False) -> str | None:
    """若应拦截则返回统一提示文案，否则 ``None``。"""
    if text is None:
        return None
    raw = text.strip()
    if not raw:
        return None

    norm = normalize_text_for_scan(raw)
    compact = compact_text_for_sensitive_scan(raw)

    for term in _CORE_TERMS:
        if _contains_term(compact, term):
            return SENSITIVE_REJECT_DETAIL

    if strict:
        for term in _STRICT_EXTRA_TERMS:
            if _contains_term(compact, term):
                return SENSITIVE_REJECT_DETAIL
        for pat in _STRICT_PATTERNS:
            if pat.search(norm) or pat.search(compact):
                return SENSITIVE_REJECT_DETAIL

    return None
