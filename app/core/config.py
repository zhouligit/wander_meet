from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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

    #: 互亿无线 APIID（空则不调用短信网关；开发环境可将验证码打日志）
    ihuyi_account: str = ""
    #: 互亿无线 APIKEY / 动态密码
    ihuyi_password: str = ""
    #: 必须与报备模板一致；使用 `{code}` 替换验证码
    ihuyi_sms_template: str = "您的验证码是：{code}。请不要把验证码泄露给其他人。"

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

