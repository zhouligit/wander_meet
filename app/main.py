from contextlib import asynccontextmanager
import logging
import time
import traceback
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging_setup import configure_logging
from app.db.session import engine, redis_client

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or uuid4().hex
    request.state.request_id = request_id
    request.state.user_id = None
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        latency_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            "request_failed method=%s path=%s latency_ms=%.2f request_id=%s user_id=%s",
            request.method,
            request.url.path,
            latency_ms,
            request_id,
            request.state.user_id,
        )
        raise

    latency_ms = (time.perf_counter() - started_at) * 1000
    log_fn = logger.warning if latency_ms >= settings.app_log_slow_ms else logger.info
    log_fn(
        "request_done method=%s path=%s status=%s latency_ms=%.2f request_id=%s user_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        latency_ms,
        request_id,
        request.state.user_id,
    )
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    user_id = getattr(request.state, "user_id", None)
    logger.error(
        "unhandled_exception request_id=%s user_id=%s method=%s path=%s error=%s traceback=%s",
        request_id,
        user_id,
        request.method,
        request.url.path,
        str(exc),
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "Internal Server Error", "data": None},
        headers={"X-Request-Id": request_id},
    )

app.include_router(api_router)

