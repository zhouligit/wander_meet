#!/usr/bin/env python3
"""对 dist/soft_registration 下鉴别材料文本做脱敏。"""
from __future__ import annotations

from pathlib import Path

FILES = (
    "source_concat_full.txt",
    "source_front.txt",
    "source_back.txt",
    "cover_template.txt",
    "end_marker.txt",
    "page_count_report.txt",
)

CONFIG_SQLALCHEMY_OLD = """    @property
    def sqlalchemy_database_uri(self) -> str:
        return (
            f"mysql+asyncmy://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
            "?charset=utf8mb4"
        )"""

CONFIG_SQLALCHEMY_NEW = """    @property
    def sqlalchemy_database_uri(self) -> str:
        # 【数据库连接 URI 已隐去】
        return "mysql+asyncmy://【已隐去】"
"""

CONFIG_REDIS_OLD = """    @property
    def redis_url(self) -> str:
        password_part = f":{self.redis_password}@" if self.redis_password else ""
        return (
            f"redis://{password_part}{self.redis_host}:"
            f"{self.redis_port}/{self.redis_db}"
        )"""

CONFIG_REDIS_NEW = """    @property
    def redis_url(self) -> str:
        # 【Redis 连接串已隐去】
        return "redis://【已隐去】"
"""

JWT_BLOCK_OLD = """def _jwt_secret_key() -> str:
    s = get_settings()
    raw = (s.jwt_secret or "").strip()
    if raw:
        return raw
    return f"{s.app_name}-{s.mysql_db}-secret"
"""

JWT_BLOCK_NEW = """def _jwt_secret_key() -> str:
    # 【JWT 密钥逻辑已隐去】
    return "【已隐去】"
"""

AUTH_SMS_BLOCK_OLD = """        account = (settings.ihuyi_account or "").strip()
        password = (settings.ihuyi_password or "").strip()
        if account and password:
            content = (settings.ihuyi_sms_template or "").replace("{code}", code)
            try:
                await asyncio.to_thread(
                    send_sms_submit_sync,
                    account,
                    password,
                    phone,
                    content,
                )"""

AUTH_SMS_BLOCK_NEW = """        account = (settings.ihuyi_account or "").strip()
        sms_cred = (settings.ihuyi_password or "").strip()
        if account and sms_cred:
            content = (settings.ihuyi_sms_template or "").replace("{code}", code)
            try:
                await asyncio.to_thread(
                    send_sms_submit_sync,
                    account,
                    sms_cred,
                    phone,
                    content,
                )"""

IHUYI_DEF_OLD = '''def send_sms_submit_sync(account: str, password: str, mobile: str, content: str) -> dict[str, Any]:
    """同步 POST `/sms/Submit.json`，成功返回解析后的 JSON dict。"""
    hostname = "api.ihuyi.com"
    request_uri = "/sms/Submit.json"
    values = {
        "account": account,
        "password": password,
        "mobile": mobile,
        "content": content,
    }'''

IHUYI_DEF_NEW = '''def send_sms_submit_sync(account: str, api_credential: str, mobile: str, content: str) -> dict[str, Any]:
    """同步 POST `/sms/Submit.json`，成功返回解析后的 JSON dict。"""
    hostname = "api.ihuyi.com"
    request_uri = "/sms/Submit.json"
    values = {
        "account": account,
        "【接口凭证字段】": api_credential,
        "mobile": mobile,
        "content": content,
    }'''


_BRAND_PLACEHOLDER = "\uE000QJL\uE001"


def normalize_product_brand(text: str) -> str:
    """鉴别材料中与登记表一致：品牌「去旅聚」（避免源程序摘录仍出现旧称「旅聚」）。"""
    text = text.replace("去旅聚", _BRAND_PLACEHOLDER)
    text = text.replace("旅聚", "去旅聚")
    return text.replace(_BRAND_PLACEHOLDER, "去旅聚")


def sanitize(text: str) -> str:
    text = text.replace('mysql_password: str = "root"', 'mysql_credential: str = "【已隐去】"')
    text = text.replace('mysql_user: str = "root"', 'mysql_user: str = "【已隐去】"')
    text = text.replace('sms_mock_code: str = "123456"', 'sms_mock_code: str = "【已隐去】"')
    text = text.replace('(settings.sms_mock_code or "123456")', '(settings.sms_mock_code or "【已隐去】")')
    text = text.replace('.strip() or "123456"', '.strip() or "【已隐去】"')

    text = text.replace("#: 互亿无线 APIKEY / 动态密码", "#: 【第三方短信接口配置说明已隐去】")
    text = text.replace(
        "#: JWT 签名密钥；为空则回退为兼容旧版的 ``{app_name}-{mysql_db}-secret``（生产务必配置）",
        "#: 【JWT 签名密钥配置说明已隐去】",
    )

    if CONFIG_SQLALCHEMY_OLD in text:
        text = text.replace(CONFIG_SQLALCHEMY_OLD, CONFIG_SQLALCHEMY_NEW)
    if CONFIG_REDIS_OLD in text:
        text = text.replace(CONFIG_REDIS_OLD, CONFIG_REDIS_NEW)
    if JWT_BLOCK_OLD in text:
        text = text.replace(JWT_BLOCK_OLD, JWT_BLOCK_NEW)

    if AUTH_SMS_BLOCK_OLD in text:
        text = text.replace(AUTH_SMS_BLOCK_OLD, AUTH_SMS_BLOCK_NEW)

    text = text.replace(
        'detail="SMS service not configured (set IHUYI_ACCOUNT / IHUYI_PASSWORD)",',
        'detail="SMS service not configured (set 【短信网关环境变量说明已隐去】)",',
    )

    if IHUYI_DEF_OLD in text:
        text = text.replace(IHUYI_DEF_OLD, IHUYI_DEF_NEW)

    text = text.replace("settings.ihuyi_password", "settings.ihuyi_credential")
    text = text.replace("ihuyi_password:", "ihuyi_credential:")
    text = text.replace("mysql_password:", "mysql_credential:")
    text = text.replace("self.mysql_password", "self.mysql_credential")
    text = text.replace("redis_password:", "redis_credential:")
    text = text.replace("self.redis_password", "self.redis_credential")
    text = text.replace("jwt_secret:", "jwt_signing_key:")
    text = text.replace("(s.jwt_secret", "(s.jwt_signing_key")
    text = text.replace("settings.jwt_secret", "settings.jwt_signing_key")

    text = text.replace(
        '    f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"',
        '    "mysql+pymysql://【已隐去】"',
    )

    # 标准库 secrets / 函数名中的 secret 字样（鉴别材料展示）
    text = text.replace("import secrets\n", "import secrets as _rnd\n")
    text = text.replace("secrets.", "_rnd.")
    text = text.replace("_jwt_secret_key", "_jwt_signing_key")

    return normalize_product_brand(text)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "dist" / "soft_registration"
    if not root.is_dir():
        raise SystemExit(f"目录不存在: {root}")

    for name in FILES:
        path = root / name
        if not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        path.write_text(sanitize(raw), encoding="utf-8")
        print("sanitized:", path)


if __name__ == "__main__":
    main()
