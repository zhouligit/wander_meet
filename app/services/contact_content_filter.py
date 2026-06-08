"""检测用户文本中的手机号、微信号等联系方式（尽力拦截，无法保证零漏报/零误伤）。"""

from __future__ import annotations

import re

from app.services.text_scan_utils import normalize_text_for_scan

CONTACT_REJECT_DETAIL = "为保护安全，请勿发送手机号、微信号等联系方式"


def _contains_mainland_mobile(normalized: str) -> bool:
    digits = "".join(c for c in normalized if c.isdigit())
    if len(digits) < 11:
        return False
    for i in range(0, len(digits) - 10):
        chunk = digits[i : i + 11]
        if re.match(r"^1[3-9]\d{9}$", chunk):
            return True
    return False


# 典型「留联系方式」短句（整段出现才拦，减少误伤）
_SOLICIT_PHRASES: tuple[str, ...] = (
    "加我微信",
    "加你微信",
    "加您微信",
    "加下微信",
    "加个人微信",
    "加我个人微信",
    "加下我微信",
    "互加微信",
    "私聊微信",
    "私加微信",
)

# 带结构 id / 号 的样式（冒号含半角、全角 U+FF1A）
_COLON = "\uFF1A:"  # 全角冒号 + 半角
# wx/vx 后 ID 至少 3 位，避免漏拦短号；与客户端 Mock 规则保持一致
_CONTACT_HINT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"微信[号\s：:]*[a-zA-Z0-9_\-]{4,32}"),
    re.compile(r"薇信[号\s：:]*[a-zA-Z0-9_\-]{4,32}"),
    re.compile(rf"(?i)wx\s*[{_COLON}：]\s*[a-zA-Z0-9_\-]{{3,32}}"),
    re.compile(rf"(?i)vx\s*[{_COLON}：]\s*[a-zA-Z0-9_\-]{{3,32}}"),
    re.compile(r"微信号[：:\s]*[a-zA-Z0-9_\-]{4,32}"),
    re.compile(r"(?i)wechat[：:\s]+[a-zA-Z0-9_\-]{4,32}"),
    re.compile(r"(?:QQ|qq)[：:\s]*\d{5,12}"),
    re.compile(r"扣扣[：:\s]*\d{5,12}"),
    re.compile(r"(?:互加|扫码加)(?:个)?微"),
)


def contact_text_blocked_reason(text: str | None) -> str | None:
    """若应拦截则返回统一提示文案，否则 ``None``。"""
    if text is None:
        return None
    raw = text.strip()
    if not raw:
        return None
    norm = normalize_text_for_scan(raw)
    if _contains_mainland_mobile(norm):
        return CONTACT_REJECT_DETAIL
    for phrase in _SOLICIT_PHRASES:
        if phrase in norm:
            return CONTACT_REJECT_DETAIL
    for pat in _CONTACT_HINT_PATTERNS:
        if pat.search(norm):
            return CONTACT_REJECT_DETAIL
    return None
