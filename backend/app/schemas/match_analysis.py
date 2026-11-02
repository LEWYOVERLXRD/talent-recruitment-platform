"""AI 匹配分析（MatchAnalysis）数据模型：请求体与响应体"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


class MatchCreateRequest(BaseModel):
    """新匹配必须明确实际输入版本。"""

    job_id: int = Field(..., description="招聘需求ID")
    candidate_id: int = Field(..., description="候选人ID")
    resume_id: int = Field(..., gt=0, description="采用的固定简历版本ID")
    expected_job_version: int = Field(..., gt=0)
    expected_skill_revision: int = Field(..., ge=0)
    model_config = ConfigDict(extra="forbid")


class ModelMatch(BaseModel):
    match_score: float | None = Field(..., ge=0, le=100, allow_inf_nan=False)
    match_points: list[StrictStr] = Field(..., max_length=20)
    mismatch_points: list[StrictStr] = Field(..., max_length=20)
    extracted_skills: list[StrictStr] = Field(..., max_length=80)
    questions_to_ask: list[StrictStr] = Field(..., max_length=20)
    summary: StrictStr | None

    @field_validator("match_score", mode="before")
    @classmethod
    def score_type(cls, value):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError("score must be a number or null")
        return value


class MatchAnalysisOut(BaseModel):
    """匹配分析结果（落库后的完整记录）"""

    id: int
    job_id: int
    candidate_id: int
    resume_id: Optional[int] = None
    analysis_text: Optional[str] = None
    extracted_skills: Optional[str] = None
    match_points: Optional[str] = None
    mismatch_points: Optional[str] = None
    questions_to_ask: Optional[str] = None
    model_used: Optional[str] = None
    match_score: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    executed_by: int | None = None
    job_version: int | None = None
    input_snapshot: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class MatchSummary(BaseModel):
    id: int
    job_id: int
    candidate_id: int
    resume_id: int | None = None
    job_version: int | None = None
    executed_by: int | None = None
    match_score: float | None = None
    model_used: str | None = None
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class MatchAnalysisListResponse(BaseModel):
    """匹配结果分页列表"""

    total: int
    items: list[MatchSummary]
