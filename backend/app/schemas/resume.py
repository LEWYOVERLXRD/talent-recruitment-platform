"""私有简历接口只暴露业务字段，不暴露存储路径。"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResumeSummary(BaseModel):
    id: int
    candidate_id: int
    version: int
    uploaded_by: int | None = None
    original_name: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    is_primary: bool
    parse_status: str
    parse_error: str | None = None
    parsed_at: datetime | None = None
    extraction_status: str
    extraction_error: str | None = None
    extracted_at: datetime | None = None
    skill_revision: int
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class ResumeDetail(ResumeSummary):
    parsed_text: str | None = None


class ResumePage(BaseModel):
    total: int
    items: list[ResumeSummary]


class PrimaryChange(BaseModel):
    expected_primary_id: int | None = Field(..., gt=0)
    model_config = ConfigDict(extra="forbid")


class SkillRevision(BaseModel):
    expected_skill_revision: int = Field(..., ge=0)
    model_config = ConfigDict(extra="forbid")


class SkillCreate(SkillRevision):
    name: str = Field(..., min_length=1, max_length=100)
    category: str | None = Field(None, max_length=50)
    evidence: str = Field(..., min_length=1, max_length=5000)


class SkillReview(SkillRevision):
    review_status: Literal["confirmed", "rejected"]
    evidence: str | None = Field(None, min_length=1, max_length=5000)


class SkillOut(BaseModel):
    id: int
    skill_id: int
    name: str
    category: str | None = None
    evidence: str
    model_used: str | None = None
    extracted_at: datetime
    review_status: str
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None


class SkillsOut(BaseModel):
    resume_id: int
    skill_revision: int
    extraction_status: str
    extraction_error: str | None = None
    items: list[SkillOut]
