"""候选人（Candidate）数据模型：创建、更新、查询响应"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.candidate import CandidateSource


class CandidateCreate(BaseModel):
    """创建候选人（猎头录入人才库）"""

    model_config = ConfigDict(extra="forbid")
    ownership: Literal["individual", "agency"] = "individual"
    owner_user_id: Optional[int] = Field(None, gt=0, description="仅管理员指定个人档案负责人；猎头不得指定他人")

    name: str = Field(..., min_length=1, max_length=50, description="候选人姓名")
    gender: Optional[str] = Field(None, max_length=10, description="性别")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    current_company: Optional[str] = Field(None, max_length=100, description="当前公司")
    current_position: Optional[str] = Field(None, max_length=100, description="当前职位")
    years_of_experience: Optional[int] = Field(None, description="工作年限")
    education: Optional[str] = Field(None, max_length=50, description="最高学历")
    expected_salary: Optional[str] = Field(None, max_length=50, description="期望薪资")
    expected_location: Optional[str] = Field(None, max_length=100, description="期望工作地")
    source: Optional[CandidateSource] = Field(
        None, description="候选人来源（默认 manual）"
    )


class CandidateUpdate(BaseModel):
    """更新候选人（仅更新传入的字段）"""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=50)
    gender: Optional[str] = Field(None, max_length=10)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    current_company: Optional[str] = Field(None, max_length=100)
    current_position: Optional[str] = Field(None, max_length=100)
    years_of_experience: Optional[int] = None
    education: Optional[str] = Field(None, max_length=50)
    expected_salary: Optional[str] = Field(None, max_length=50)
    expected_location: Optional[str] = Field(None, max_length=100)
    source: Optional[CandidateSource] = None


class CandidateOut(BaseModel):
    """候选人响应"""

    id: int
    name: str
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    current_company: Optional[str] = None
    current_position: Optional[str] = None
    years_of_experience: Optional[int] = None
    education: Optional[str] = None
    expected_salary: Optional[str] = None
    expected_location: Optional[str] = None
    source: CandidateSource
    created_by: Optional[int] = None
    provider_id: Optional[int] = None
    provider_kind: Optional[str] = None
    agency_id: Optional[int] = None
    owner_user_id: Optional[int] = None
    candidate_user_id: Optional[int] = None
    owner_username: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CandidateListResponse(BaseModel):
    """候选人分页列表"""

    total: int
    items: list[CandidateOut]


class CandidateTransfer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_user_id: int = Field(gt=0)
