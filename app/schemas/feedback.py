from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

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
    """前端 JSON 多为 camelCase；scene 缺省为 other，仅需 description。"""

    model_config = ConfigDict(populate_by_name=True)

    scene: FeedbackScene = Field(default="other")
    description: str = Field(min_length=10, max_length=500)
    expectation: str = Field(default="", max_length=500)
    contact_willing: bool = Field(
        default=False,
        validation_alias=AliasChoices("contact_willing", "contactWilling"),
    )
    contact_note: str = Field(
        default="",
        max_length=160,
        validation_alias=AliasChoices("contact_note", "contactNote"),
    )
    app_version: str = Field(
        default="",
        max_length=32,
        validation_alias=AliasChoices("app_version", "appVersion"),
    )
    platform: str = Field(default="mp-weixin", max_length=16)


class UserFeedbackCreateData(BaseModel):
    feedbackId: str
