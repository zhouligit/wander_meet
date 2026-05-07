"""互亿无线文本短信 Submit.json（单条发送）。"""

from __future__ import annotations

import http.client
import json
import logging
import urllib.parse
from typing import Any

logger = logging.getLogger(__name__)


class IhuiSmsError(Exception):
    """互亿接口返回业务失败或非预期响应。"""


def send_sms_submit_sync(account: str, password: str, mobile: str, content: str) -> dict[str, Any]:
    """同步 POST `/sms/Submit.json`，成功返回解析后的 JSON dict。"""
    hostname = "api.ihuyi.com"
    request_uri = "/sms/Submit.json"
    values = {
        "account": account,
        "password": password,
        "mobile": mobile,
        "content": content,
    }
    params = urllib.parse.urlencode(values).encode("utf-8")
    headers = {
        "Content-type": "application/x-www-form-urlencoded",
        "Accept": "text/plain",
    }
    conn = http.client.HTTPSConnection(hostname, timeout=30)
    status = 0
    raw = ""
    try:
        conn.request("POST", request_uri, params, headers)
        response = conn.getresponse()
        status = response.status
        raw = response.read().decode("utf-8")
    finally:
        conn.close()

    if status != 200:
        raise IhuiSmsError(f"HTTP {status}: {raw[:200]}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IhuiSmsError(f"无效响应：{raw[:200]}") from exc

    # 互亿常见：code==2 为提交成功（以控制台文档为准）
    code = data.get("code")
    if code in (2, "2"):
        return data

    msg = data.get("msg") or data.get("message") or raw
    raise IhuiSmsError(str(msg))
