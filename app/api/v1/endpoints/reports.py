from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.db.session import get_db_session
from app.models.report import Report
from app.models.user import User
from app.schemas.common import APIResponse
from app.schemas.report import (
    ReportCreateData,
    ReportCreateRequest,
    ReportItem,
    ReportListData,
)

router = APIRouter(tags=["reports"])


@router.post("/reports")
async def create_report(
    payload: ReportCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ReportCreateData]:
    report = Report(
        reporter_id=current_user.id,
        target_type=payload.targetType,
        target_id=payload.targetId,
        activity_id=int(payload.activityId[4:]) if payload.activityId and payload.activityId.startswith("act_") else None,
        reason_code=payload.reasonCode,
        detail=payload.detail,
        status="pending",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return APIResponse(data=ReportCreateData(reportId=f"rpt_{report.id}", status=report.status))


@router.get("/me/reports")
async def my_reports(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[ReportListData]:
    total = (
        await db.execute(select(func.count(Report.id)).where(Report.reporter_id == current_user.id))
    ).scalar_one()
    rows = (
        (
            await db.execute(
                select(Report)
                .where(Report.reporter_id == current_user.id)
                .order_by(Report.id.desc())
                .offset((page - 1) * pageSize)
                .limit(pageSize)
            )
        )
        .scalars()
        .all()
    )
    return APIResponse(
        data=ReportListData(
            list=[
                ReportItem(
                    reportId=f"rpt_{r.id}",
                    targetType=r.target_type,
                    reasonCode=r.reason_code,
                    status=r.status,
                    createdAt=r.created_at,
                    handledResult=r.handled_action,
                )
                for r in rows
            ],
            total=total,
            page=page,
            pageSize=pageSize,
        )
    )


@router.get("/admin/reports")
async def admin_reports(
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_admin_user),
) -> APIResponse[ReportListData]:
    filters = []
    if status in {"pending", "handled"}:
        filters.append(Report.status == status)
    total = (await db.execute(select(func.count(Report.id)).where(*filters))).scalar_one()
    rows = (
        (
            await db.execute(
                select(Report)
                .where(*filters)
                .order_by(Report.id.desc())
                .offset((page - 1) * pageSize)
                .limit(pageSize)
            )
        )
        .scalars()
        .all()
    )
    return APIResponse(
        data=ReportListData(
            list=[
                ReportItem(
                    reportId=f"rpt_{r.id}",
                    targetType=r.target_type,
                    reasonCode=r.reason_code,
                    status=r.status,
                    createdAt=r.created_at,
                    handledResult=r.handled_action,
                )
                for r in rows
            ],
            total=total,
            page=page,
            pageSize=pageSize,
        )
    )


@router.patch("/admin/reports/{report_id}")
async def admin_handle_report(
    report_id: str,
    action: str,
    note: str | None = None,
    notifyUser: bool | None = None,
    db: AsyncSession = Depends(get_db_session),
    admin_user: User = Depends(get_admin_user),
) -> APIResponse[dict[str, str]]:
    _ = note, notifyUser
    rid = int(report_id[4:]) if report_id.startswith("rpt_") else int(report_id)
    report = await db.scalar(select(Report).where(Report.id == rid))
    if not report:
        return APIResponse(code=404, message="report not found", data={"status": "not_found"})
    report.status = "handled"
    report.handled_action = action
    report.handler_admin_id = admin_user.id
    report.handled_at = datetime.now(UTC)
    await db.commit()
    return APIResponse(data={"status": "handled"})

