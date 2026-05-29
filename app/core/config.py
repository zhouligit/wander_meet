from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _lower_strip(v):
    if v is None:
        return "ihuyi"
    if isinstance(v, str):
        s = v.strip().lower()
        return s if s in ("ihuyi", "aliyun") else "ihuyi"
    return v


class Settings(BaseSettings):
    #: 忽略 .env 中已废弃或未声明的键（例如旧版互亿 ``IHUYI_*``），避免升级后 Alembic / 应用启动报 ValidationError
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "WanderMeet API"
    app_env: str = "dev"
    app_debug: bool = True
    app_log_slow_ms: int = 300
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_cors_origins: str = "http://localhost:5173,http://localhost:5174"
    sqlalchemy_echo: bool | None = None

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "root"
    mysql_db: str = "wandermeet"
    #: 连接池回收周期（秒）。须 **小于** MySQL ``wait_timeout``（常见 28800≈8h），否则服务端会先掐连接，
    #: 池里归还连接时可能出现 ``BrokenPipeError``。云数据库若空闲超时较短（如 60s），请改为 ``55`` 等。
    mysql_pool_recycle_seconds: int = 28000
    #: 异步引擎连接池大小（每 worker 常驻连接数）。小内存机可保持默认 3；高并发可调大并与 ``max_connections`` 对齐。
    mysql_pool_size: int = 3
    #: 超出 pool_size 时允许的临时连接上限。单 worker 峰值连接 ≈ pool_size + max_overflow。
    mysql_max_overflow: int = 2

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    #: ``GET /activities`` 同城列表 Redis 短缓存（见 doc/PERF_Cache_and_Scale.md）
    cache_activity_list_enabled: bool = True
    cache_activity_list_ttl_seconds: int = 60

    #: 鉴权用户行 Redis 缓存（``get_current_user``）
    cache_user_auth_enabled: bool = True
    cache_user_auth_ttl_seconds: int = 300
    #: ``GET /me``、``GET /me/stats`` Redis 短缓存
    cache_me_enabled: bool = True
    cache_me_ttl_seconds: int = 30
    #: ``GET /meta/*`` 静态接口 HTTP Cache-Control max-age（秒）；0=不设置
    meta_http_cache_max_age_seconds: int = 3600

    #: 非 Mock 时短信渠道：``ihuyi``=互亿无线（默认），``aliyun``=阿里云 SendSms
    sms_provider: Annotated[Literal["ihuyi", "aliyun"], BeforeValidator(_lower_strip)] = "ihuyi"

    #: 互亿无线 APIID（``SMS_PROVIDER=ihuyi`` 且 ``SMS_USE_MOCK=false`` 时必填）
    ihuyi_account: str = ""
    #: 互亿无线 APIKEY / 接口密码
    ihuyi_password: str = ""
    #: 须与报备模板一致；使用 ``{code}`` 替换验证码
    ihuyi_sms_template: str = "您的验证码是：{code}。请不要把验证码泄露给其他人。"

    #: 阿里云 AccessKey（``SMS_PROVIDER=aliyun`` 时使用）
    aliyun_access_key_id: str = ""
    aliyun_access_key_secret: str = ""
    #: 短信签名（控制台已审核通过的签名，须与模板归属一致）
    aliyun_sms_sign_name: str = ""
    #: 短信模板 CODE，如 ``SMS_123456789``（模板变量 JSON 的 key 须与控制台变量名一致，常见为 ``code``）
    aliyun_sms_template_code: str = ""
    #: API 接入域名，默认 ``dysmsapi.aliyuncs.com``；与 OpenAPI 文档一致 https://next.api.aliyun.com/api/Dysmsapi/2017-05-25/SendSms
    aliyun_sms_endpoint: str = "dysmsapi.aliyuncs.com"
    #: 地域 ID，短信国内线路常用 ``cn-hangzhou``（与控制台开通地域一致即可）
    aliyun_sms_region_id: str = "cn-hangzhou"
    #: 若控制台模板含 ``${minute}`` 等变量，除 ``code`` 外再传有效分钟数（与 ``sms_code_ttl_seconds`` 对齐）
    aliyun_sms_template_include_minute: bool = False

    #: 短信验证码在 Redis 中的有效期（秒），默认 300=5 分钟
    sms_code_ttl_seconds: int = 300
    #: 同一手机号两次「发送验证码」最小间隔（秒），须与前端重发倒计时一致
    sms_send_min_interval_seconds: int = 60

    #: 测试阶段为 True：不发短信、不扣费，验证码固定为 ``sms_mock_code``（上线前务必改为 False）
    sms_use_mock: bool = True
    #: Mock 验证码（仅当 ``sms_use_mock`` 为 True 时写入 Redis）
    sms_mock_code: str = "123456"

    #: JWT 签名密钥；为空则回退为兼容旧版的 ``{app_name}-{mysql_db}-secret``（生产务必配置）
    jwt_secret: str = ""

    #: Access JWT 有效期（秒）
    access_token_expires_seconds: int = 7200
    #: Refresh token（Redis）有效期（秒），默认 7 天
    refresh_token_expires_seconds: int = 604800

    #: 发验证码：同一 IP 每分钟最多次数（0=不限制）
    auth_sms_ip_limit_per_minute: int = 30
    #: 短信登录：同一 IP 每分钟最多次数（0=不限制）
    auth_login_ip_limit_per_minute: int = 120
    #: 微信登录：同一 IP 每分钟最多次数（0=不限制）
    auth_wechat_login_ip_limit_per_minute: int = 120
    auth_douyin_login_ip_limit_per_minute: int = 120
    #: 邮箱注册：同一 IP 每分钟最多次数（0=不限制）
    auth_email_register_ip_limit_per_minute: int = 20
    #: 邮箱登录：同一 IP 每分钟最多次数（0=不限制）
    auth_email_login_ip_limit_per_minute: int = 60
    #: 同一邮箱两次注册请求最小间隔（秒）
    auth_email_register_min_interval_seconds: int = 60
    #: 连续登录失败多少次后临时锁定
    auth_email_login_max_failures: int = 5
    #: 登录失败锁定秒数
    auth_email_login_lock_seconds: int = 900
    #: 忘记密码：同一 IP 每分钟最多次数（0=不限制）
    auth_email_forgot_ip_limit_per_minute: int = 10
    #: 同一邮箱两次「忘记密码」发信最小间隔（秒）
    auth_email_forgot_min_interval_seconds: int = 60
    #: 重置密码验证码有效秒数
    auth_email_reset_code_ttl_seconds: int = 900

    #: 发信：测试 true 只打日志不发邮件
    email_use_mock: bool = True
    #: Mock 下固定验证码（空则 123456）
    email_mock_code: str = "123456"
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_ssl: bool = True
    smtp_starttls: bool = False
    email_reset_subject: str = "去旅聚 重置密码验证码"
    email_reset_body_template: str = (
        "您正在重置去旅聚账号密码，验证码为：{code}，{minutes} 分钟内有效。如非本人操作请忽略。"
    )

    #: 百度 BOS（头像等用户资源，见 app/services/bos_storage.py）
    bos_access_key_id: str = ""
    bos_secret_access_key: str = ""
    bos_bucket: str = ""
    #: 如 https://bj.bcebos.com 或 https://bucket-name.bj.bcebos.com
    bos_endpoint: str = "https://bj.bcebos.com"
    #: 公网访问根 URL（Bucket 域名或 CDN），如 https://your-bucket.bj.bcebos.com
    bos_public_base_url: str = ""
    bos_avatar_max_bytes: int = 5 * 1024 * 1024
    bos_chat_image_max_bytes: int = 8 * 1024 * 1024
    bos_presign_expires_seconds: int = 1800

    #: 微信小程序 AppID / AppSecret（``auth/wechat/login`` 调 jscode2session）
    wx_mp_appid: str = ""
    wx_mp_appsecret: str = ""
    #: 本地/测试：不调微信，用 ``code`` 派生固定 openid（上线务必 false）
    wx_mp_use_mock: bool = False

    #: 抖音小程序 AppID / AppSecret（``auth/douyin/login`` 调 code2session）
    dy_mp_appid: str = ""
    dy_mp_appsecret: str = ""
    dy_mp_use_mock: bool = False

    #: 支付通道：wechat（官方 APIv3，默认）| yungou（遗留备选，后期可下线）
    pay_provider: str = "wechat"
    #: 微信支付 APIv3（见 doc/wx_pay.md）
    wechat_pay_mch_id: str = ""
    wechat_pay_api_v3_key: str = ""
    wechat_pay_cert_serial: str = ""
    wechat_pay_private_key_path: str = ""
    wechat_pay_private_key: str = ""
    wechat_pay_notify_url: str = ""
    wechat_pay_use_mock: bool = False

    #: YunGouOS 微信聚合支付（遗留，PAY_PROVIDER=yungou 时使用）
    yungou_mch_id: str = ""
    yungou_api_key: str = ""
    yungou_native_api: str = "https://api.pay.yungouos.com/api/pay/wxpay/nativePay"
    yungou_minapp_api: str = "https://api.pay.yungouos.com/api/pay/wxpay/minAppPay"
    #: 支付结果回调完整 URL（须公网 HTTPS，如 https://域名/api/v1/wm/pay/yungou/notify）
    yungou_notify_url: str = ""
    yungou_use_mock: bool = False
    #: 是否启用完整多步新手引导；``false`` 时登录后仅要求昵称+性别（见产品文档）
    onboarding_full_enabled: bool = False
    #: 是否启用「发布活动前付费」；``false`` 时前端跳过支付（POST /activities 本身不校验支付单）
    pay_publish_enabled: bool = False
    pay_publish_fee_yuan: str = "0.10"
    pay_publish_body: str = "发布活动"
    pay_publish_product: str = "publish"
    pay_order_ttl_seconds: int = 1800
    yungou_pay_success_code: str = "1"

    @property
    def sqlalchemy_database_uri(self) -> str:
        return (
            f"mysql+asyncmy://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
            "?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        password_part = f":{self.redis_password}@" if self.redis_password else ""
        return (
            f"redis://{password_part}{self.redis_host}:"
            f"{self.redis_port}/{self.redis_db}"
        )

    @property
    def cors_origins(self) -> list[str]:
        if not self.app_cors_origins:
            return []
        return [origin.strip() for origin in self.app_cors_origins.split(",") if origin.strip()]

    @property
    def sql_echo(self) -> bool:
        if self.sqlalchemy_echo is not None:
            return self.sqlalchemy_echo
        return self.app_debug and self.app_env.lower() != "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()

