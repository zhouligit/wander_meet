from typing import Literal

from pydantic import BaseModel, Field

FeedbackScene = Literal[
    "find_activity",
    "login",
    "enroll",
    "chat",
    "city_hall",
    "place_search",
    "publish",
    "profile",
    "suggestion",
    "other",
]


class CreateUserFeedbackRequest(BaseModel):
    scene: FeedbackScene
    description: str = Field(min_length=10, max_length=500)
    expectation: str = Field(default="", max_length=500)
    contactWilling: bool = False
    contactNote: str = Field(default="", max_length=160)
    appVersion: str = Field(default="", max_length=32)
    platform: str = Field(default="mp-weixin", max_length=16)


class UserFeedbackCreateData(BaseModel):
    feedbackId: str
