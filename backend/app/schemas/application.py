"""求职投递接口模型。"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: int = Field(gt=0)
    resume_id: int = Field(gt=0)
    assignment_id: int = Field(gt=0)


class ApplicationStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["screening", "interview", "offer", "rejected"]
    rejection_reason_category: str | None = Field(None, max_length=50)
    rejection_reason_note: str | None = Field(None, max_length=2000)


class ApplicationReviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["pending", "not_recommended"]
    review_note: str | None = Field(None, max_length=2000)


class ApplicationMineOut(BaseModel):
    id: int
    job_id: int
    job_title: str
    client_company_name: str | None = None
    resume_id: int | None
    resume_name: str | None = None
    status: str
    source: str
    submitted_at: datetime
    status_updated_at: datetime
    created_at: datetime | None = None
    review_status: str | None = None
    assignment_id: int | None = None
    record_kind: str = "primary"
    visibility_message: str | None = None


class ApplicationInternalOut(ApplicationMineOut):
    candidate_id: int | None
    applicant_user_id: int | None
    candidate_name: str
    rejection_reason_category: str | None = None
    rejection_reason_note: str | None = None
    publisher_user_id: int | None = None
    review_note: str | None = None
    can_recommend: bool = False
    working_candidate_id: int | None = None
