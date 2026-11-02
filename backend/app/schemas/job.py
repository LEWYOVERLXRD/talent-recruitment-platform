"""招聘需求（Job/JD）数据模型：创建、更新、查询响应"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.job import JobSource, JobStatus


class JobCreate(BaseModel):
    """创建客户草稿；招聘方从账号企业取客户，猎头须选择已核验企业。"""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=100, description="需求/岗位名称")
    department: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    location: Optional[str] = None
    job_profile_content: Optional[str] = Field(None, min_length=1)

    client_company_id: Optional[int] = Field(None, gt=0, description="已有客户企业ID；企业招聘方不得指定")
    contact_person: Optional[str] = Field(None, max_length=50, description="客户联系人")
    contact_info: Optional[str] = Field(None, max_length=100, description="联系方式")
    hiring_count: Optional[int] = Field(None, description="招聘人数")
    priority: Optional[str] = Field(None, description="优先级 high/normal/low")


class JobUpdate(BaseModel):
    """更新招聘需求（仅更新传入的字段）"""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(gt=0)
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    location: Optional[str] = None
    contact_person: Optional[str] = None
    contact_info: Optional[str] = None
    hiring_count: Optional[int] = None
    priority: Optional[str] = None

    @model_validator(mode="after")
    def has_change(self):
        if len(self.model_fields_set - {"expected_version"}) == 0:
            raise ValueError("至少提供一个更新字段")
        if "title" in self.model_fields_set and not (self.title or "").strip():
            raise ValueError("岗位名称不能为空")
        return self


class JobConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(gt=0)


class JobStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(gt=0)
    status: JobStatus
    reason: Optional[str] = Field(None, max_length=1000)


class ClientCompanyOption(BaseModel):
    id: int
    name: str


class JobProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    raw_content: str
    source_type: str
    version: int
    submitted_by: Optional[int] = None
    submitted_at: datetime


class JobOut(BaseModel):
    """招聘需求响应（含客户企业名称冗余）"""

    id: int
    title: str
    department: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    location: Optional[str] = None
    status: JobStatus
    source: JobSource
    client_company_id: int
    client_company_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_info: Optional[str] = None
    hiring_count: Optional[int] = None
    priority: Optional[str] = None
    created_by: Optional[int] = None
    job_profile_id: Optional[int] = None
    version: int = 1
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    ever_confirmed_at: Optional[datetime] = None
    has_current_authorization: bool = False
    receivers: list[dict] = []
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    """招聘需求分页列表"""

    total: int
    items: list[JobOut]
