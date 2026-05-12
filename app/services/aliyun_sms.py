"""阿里云短信服务 SendSms（OpenAPI Dysmsapi 2017-05-25）。

文档与调试入口：https://next.api.aliyun.com/api/Dysmsapi/2017-05-25/SendSms
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class AliyunSmsError(Exception):
    """阿里云 SendSms 返回非 OK 或调用失败。"""


def send_sms_aliyun_sync(
    access_key_id: str,
    access_key_secret: str,
    *,
    endpoint: str,
    region_id: str,
    phone_numbers: str,
    sign_name: str,
    template_code: str,
    template_param: dict[str, Any],
) -> dict[str, Any]:
    """同步调用 SendSms。``template_param`` 的 key 须与控制台短信模板变量名一致（常见为 ``code``）。"""
    from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
    from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_tea_util import models as util_models

    config = open_api_models.Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        region_id=region_id,
    )
    config.endpoint = endpoint
    client = Dysmsapi20170525Client(config)
    req = dysmsapi_20170525_models.SendSmsRequest(
        phone_numbers=phone_numbers,
        sign_name=sign_name,
        template_code=template_code,
        template_param=json.dumps(template_param, ensure_ascii=True),
    )
    runtime = util_models.RuntimeOptions()
    try:
        resp = client.send_sms_with_options(req, runtime)
    except Exception as exc:
        logger.exception("Aliyun SendSms request failed")
        raise AliyunSmsError(str(exc)) from exc

    body = getattr(resp, "body", None)
    if body is None:
        raise AliyunSmsError("empty response body")
    code = getattr(body, "code", None)
    if code == "OK":
        return {
            "Code": code,
            "Message": getattr(body, "message", None) or "",
            "BizId": getattr(body, "biz_id", None) or "",
        }
    msg = getattr(body, "message", None) or str(body)
    raise AliyunSmsError(f"{code}: {msg}")
