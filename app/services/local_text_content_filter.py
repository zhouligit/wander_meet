"""本地 UGC 文本过滤：联系方式 + 敏感词（先于/独立于微信 msgSecCheck）。"""

from __future__ import annotations

from app.services.contact_content_filter import contact_text_blocked_reason
from app.services.sensitive_content_filter import sensitive_text_blocked_reason


def local_text_blocked_reason(text: str | None, *, strict: bool = False) -> str | None:
    """若应拦截则返回提示文案（联系方式或敏感词），否则 ``None``。"""
    blocked = contact_text_blocked_reason(text)
    if blocked:
        return blocked
    return sensitive_text_blocked_reason(text, strict=strict)
