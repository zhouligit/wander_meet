from fastapi import APIRouter

from app.api.v1.endpoints.activities import router as activities_router
from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.blocks import router as blocks_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.me import router as me_router
from app.api.v1.endpoints.meta import router as meta_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.reports import router as reports_router
from app.api.v1.endpoints.verification import router as verification_router

api_router = APIRouter(prefix="/api/v1/wm")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(activities_router)
api_router.include_router(me_router)
api_router.include_router(meta_router)
api_router.include_router(verification_router)
api_router.include_router(reports_router)
api_router.include_router(blocks_router)
api_router.include_router(notifications_router)
api_router.include_router(admin_router)

