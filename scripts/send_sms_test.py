#!/usr/bin/env python3
"""本地测阿里云短信：在项目根目录执行

  python scripts/send_sms_test.py 13800138000

依赖 .env 中的 ALIYUN_*（或改下面常量）。签名/模板须已审核通过。
"""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# PHONE = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("SMS_TEST_PHONE", "")).strip()
AK = os.getenv("ALIYUN_ACCESS_KEY_ID", "").strip()
SK = os.getenv("ALIYUN_ACCESS_KEY_SECRET", "").strip()
SIGN = os.getenv("ALIYUN_SMS_SIGN_NAME", "").strip()
TPL = os.getenv("ALIYUN_SMS_TEMPLATE_CODE", "").strip()
CODE = os.getenv("SMS_MOCK_CODE", "123456").strip() or "123456"
AK = 'xxxxx'
SK = 'xxxxx'

PHONE = '18210063791'
SIGN = '枣庄禾跃科技'
TPL = 'SMS_506275366'
if not PHONE:
    sys.exit("用法: python scripts/send_sms_test.py <手机号>")
if not all([AK, SK, SIGN, TPL]):
    sys.exit("请在 .env 配置 ALIYUN_ACCESS_KEY_ID/SECRET、ALIYUN_SMS_SIGN_NAME、ALIYUN_SMS_TEMPLATE_CODE")

from alibabacloud_dysmsapi20170525.client import Client
from alibabacloud_dysmsapi20170525 import models
from alibabacloud_tea_openapi import models as open_api_models

cfg = open_api_models.Config(access_key_id=AK, access_key_secret=SK, region_id="cn-hangzhou")
cfg.endpoint = "dysmsapi.aliyuncs.com"
req = models.SendSmsRequest(
    phone_numbers=PHONE,
    sign_name=SIGN,
    template_code=TPL,
    template_param=json.dumps({"code": CODE}, ensure_ascii=True),
)
resp = Client(cfg).send_sms(req)
body = resp.body
print(json.dumps({"Code": body.code, "Message": body.message, "BizId": body.biz_id}, ensure_ascii=False))
