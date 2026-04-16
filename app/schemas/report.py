from datetime import datetime

from pydantic import BaseModel


class ReportCreateRequest(BaseModel):
    targetType: str
    targetId: str
    activityId: str | None = None
    reasonCode: str
    detail: str | None = None


class ReportCreateData(BaseModel):
    reportId: str
    status: str


class ReportItem(BaseModel):
    reportId: str
    targetType: str
    reasonCode: str
    status: str
    createdAt: datetime
    handledResult: str | None = None


class ReportListData(BaseModel):
    list: list[ReportItem]
    total: int
    page: int
    pageSize: int

