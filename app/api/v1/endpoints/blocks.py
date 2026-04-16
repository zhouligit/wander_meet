from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.models.user_block import UserBlock
from app.schemas.block import BlockCreateRequest, BlockData, BlockListData, BlockListItem
from app.schemas.common import APIResponse

router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.post("")
async def create_block(
    payload: BlockCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[BlockData]:
    blocked_id = _parse_user_id(payload.blockedUserId)
    if blocked_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    block = UserBlock(blocker_id=current_user.id, blocked_id=blocked_id)
    db.add(block)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Already blocked") from exc
    return APIResponse(data=BlockData(blockedUserId=f"u_{blocked_id}"))


@router.delete("/{blocked_user_id}")
async def delete_block(
    blocked_user_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict[str, bool]]:
    blocked_id = _parse_user_id(blocked_user_id)
    block = await db.scalar(
        select(UserBlock).where(
            UserBlock.blocker_id == current_user.id,
            UserBlock.blocked_id == blocked_id,
        )
    )
    if block:
        await db.delete(block)
        await db.commit()
    return APIResponse(data={"ok": True})


@router.get("")
async def list_blocks(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[BlockListData]:
    rows = (
        (
            await db.execute(
                select(UserBlock, User)
                .join(User, User.id == UserBlock.blocked_id)
                .where(UserBlock.blocker_id == current_user.id)
                .order_by(UserBlock.id.desc())
            )
        )
        .all()
    )
    return APIResponse(
        data=BlockListData(
            list=[
                BlockListItem(
                    blockedUserId=f"u_{u.id}",
                    nickname=u.nickname,
                    avatarUrl=u.avatar_url,
                    createdAt=b.created_at,
                )
                for b, u in rows
            ]
        )
    )


def _parse_user_id(user_id: str) -> int:
    if user_id.startswith("u_"):
        user_id = user_id[2:]
    if not user_id.isdigit():
        raise HTTPException(status_code=400, detail="Invalid user id")
    return int(user_id)

