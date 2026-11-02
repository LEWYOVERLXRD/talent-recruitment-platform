"""猎头沟通、推荐固定交付与客户反馈契约。"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CommunicationCreate(BaseModel):
    job_id: int | None = Field(None, gt=0)
    comm_type: Literal["call", "wechat", "email", "other"] = "wechat"
    content: str = Field(..., min_length=1, max_length=10000)
    result: Literal["considering", "not_interested", "undecided"] | None = None
    communicated_at: datetime
    follow_up_at: datetime | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def nonblank_content(cls, value):
        if not value.strip():
            raise ValueError("沟通内容不能为空")
        return value.strip()


class CommunicationOut(BaseModel):
    id: int
    candidate_id: int
    job_id: int | None
    comm_type: str
    content: str | None
    result: str | None
    communicated_at: datetime | None
    follow_up_at: datetime | None
    created_by: int | None
    created_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class CommunicationPage(BaseModel):
    total: int
    items: list[CommunicationOut]


class RecommendationCreate(BaseModel):
    assignment_id: int = Field(..., gt=0)
    candidate_id: int = Field(..., gt=0)
    model_config = ConfigDict(extra="forbid")


class ApplicationRecommendationCreate(BaseModel):
    assignment_id: int = Field(..., gt=0)
    model_config = ConfigDict(extra="forbid")


class RecommendationUpdate(BaseModel):
    expected_version: int = Field(..., ge=1)
    resume_id: int | None = Field(None, gt=0)
    communication_id: int | None = Field(None, gt=0)
    recommendation_note: str | None = Field(None, max_length=10000)
    model_config = ConfigDict(extra="forbid")


class RecommendationStage(BaseModel):
    expected_version: int = Field(..., ge=1)
    status: Literal["contacted", "pending_recommend"]
    communication_id: int = Field(..., gt=0)
    model_config = ConfigDict(extra="forbid")


class RecommendationRefresh(BaseModel):
    expected_version: int = Field(..., ge=1)
    job_version: int = Field(..., gt=0)
    assignment_round: int = Field(..., gt=0)
    model_config = ConfigDict(extra="forbid")


class RecommendationSubmit(BaseModel):
    expected_version: int = Field(..., ge=1)
    share_basis: str = Field(..., min_length=1, max_length=5000)
    share_confirmed_at: datetime
    model_config = ConfigDict(extra="forbid")


class RecommendationFeedbackCreate(BaseModel):
    expected_version: int = Field(..., ge=1)
    conclusion: Literal["accepted", "rejected", "interviewing", "passed", "note"]
    feedback_type: Literal["recommendation", "interview"]
    content: str = Field(..., min_length=1, max_length=5000)
    model_config = ConfigDict(extra="forbid")


class RecommendationFeedbackOut(BaseModel):
    id: int
    recommendation_id: int
    actor_id: int
    feedback_type: str
    conclusion: str
    content: str
    from_status: str
    to_status: str
    recommendation_version: int
    created_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class RecommendationPage(BaseModel):
    total: int
    items: list[dict]


class RecommendationDetail(BaseModel):
    data: dict


class RecommendationFeedbackPage(BaseModel):
    total: int
    items: list[RecommendationFeedbackOut]
