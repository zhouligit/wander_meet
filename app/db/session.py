import logging
from collections.abc import AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_kw = {
    "pool_pre_ping": True,
    "pool_reset_on_return": "rollback",
    "echo": settings.sql_echo,
    "pool_size": settings.mysql_pool_size,
    "max_overflow": settings.mysql_max_overflow,
}
# 主动轮换连接，避免 MySQL 先断开空闲 TCP 后池中仍为「半死不活」连接，归还池时 close 触发 Broken pipe
if settings.mysql_pool_recycle_seconds > 0:
    _kw["pool_recycle"] = settings.mysql_pool_recycle_seconds

engine = create_async_engine(settings.sqlalchemy_database_uri, **_kw)
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

redis_client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def shutdown_db() -> None:
    """释放连接池；systemd/uvicorn 重启时偶发「TCPTransport closed」可忽略。"""
    try:
        await engine.dispose()
    except RuntimeError as exc:
        # asyncmy 在连接已被 MySQL/内核关闭后仍尝试写 QUIT，多见于 SIGTERM 关停
        if "TCPTransport closed" in str(exc) or "handler is closed" in str(exc):
            logger.warning("MySQL pool dispose on shutdown (stale socket): %s", exc)
        else:
            raise
    except Exception:
        logger.exception("MySQL engine dispose failed")

