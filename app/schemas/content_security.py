from pydantic import BaseModel, Field


class ContentSecCheckRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    scene: int = Field(default=4, ge=1, le=4)


class ContentSecCheckData(BaseModel):
    safe: bool = True
