from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import SessionLocal, redis_client

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/deps", summary="Dependency check (MySQL + Redis)")
async def deps_health() -> dict[str, str]:
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    await redis_client.ping()
    return {"status": "ok"}

