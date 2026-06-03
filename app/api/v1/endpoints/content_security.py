"""小程序发布前内容安全检测（对接微信 ``msgSecCheck``）。"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.content_security import ContentSecCheckData, ContentSecCheckRequest
from app.services.content_moderation import assert_text_content_safe

router = APIRouter(tags=["content-security"])


@router.post("/content/sec-check")
async def content_sec_check(
    payload: ContentSecCheckRequest,
    current_user: User = Depends(get_current_user),
) -> APIResponse[ContentSecCheckData]:
    """发布前文本安全检测；违规返回 400 + 统一提示文案。"""
    await assert_text_content_safe(current_user, payload.content, scene=payload.scene)
    return APIResponse(data=ContentSecCheckData(safe=True))
