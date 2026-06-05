from fastapi import APIRouter

from app.api.v1.endpoints.activities import router as activities_router
from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.blocks import router as blocks_router
from app.api.v1.endpoints.city_groups import admin_router as city_group_hosts_admin_router
from app.api.v1.endpoints.city_groups import router as city_groups_router
from app.api.v1.endpoints.direct_chats import router as direct_chats_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.me import router as me_router
from app.api.v1.endpoints.meta import router as meta_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.pay import router as pay_router
from app.api.v1.endpoints.reports import router as reports_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.verification import router as verification_router
from app.api.v1.endpoints.content_security import router as content_security_router
from app.api.v1.endpoints.feed import router as feed_router
from app.api.v1.endpoints.growth_trust import (
    act_router as growth_trust_act_router,
    content_router as growth_trust_content_router,
    me_router as growth_trust_me_router,
)

api_router = APIRouter(prefix="/api/v1/wm")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(activities_router)
api_router.include_router(city_groups_router)
api_router.include_router(city_group_hosts_admin_router)
api_router.include_router(me_router)
api_router.include_router(users_router)
api_router.include_router(meta_router)
api_router.include_router(verification_router)
api_router.include_router(reports_router)
api_router.include_router(blocks_router)
api_router.include_router(direct_chats_router)
api_router.include_router(notifications_router)
api_router.include_router(admin_router)
api_router.include_router(pay_router)
api_router.include_router(growth_trust_me_router)
api_router.include_router(growth_trust_act_router)
api_router.include_router(growth_trust_content_router)
api_router.include_router(feed_router)
api_router.include_router(content_security_router)

