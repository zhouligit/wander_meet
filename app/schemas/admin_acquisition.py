from pydantic import BaseModel


class AdminAcquisitionStatItem(BaseModel):
    source: str
    count: int
    pct: float


class AdminAcquisitionStatsData(BaseModel):
    totalUsers: int
    withSource: int
    withoutSource: int
    items: list[AdminAcquisitionStatItem]
