"""招聘需求（Job/JD）数据模型：创建、更新、查询响应"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobSource, JobStatus


class JobCreate(BaseModel):
    """创建招聘需求（双入口：企业方 / 猎头代建档）"""

    title: str = Field(..., min_length=1, max_length=100, description="需求/岗位名称")
    department: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    location: Optional[str] = None

    # 客户企业：企业方创建时由后端强制取本企业；猎头创建时通过名称动态获取/新建
    client_company_name: Optional[str] = Field(
        None, max_length=100, description="客户企业名称（猎头代客户建档时必填）"
    )
    contact_person: Optional[str] = Field(None, max_length=50, description="客户联系人")
    contact_info: Optional[str] = Field(None, max_length=100, description="联系方式")
    hiring_count: Optional[int] = Field(None, description="招聘人数")
    priority: Optional[str] = Field(None, description="优先级 high/normal/low")


class JobUpdate(BaseModel):
    """更新招聘需求（仅更新传入的字段）"""

    title: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    location: Optional[str] = None
    status: Optional[JobStatus] = None
    contact_person: Optional[str] = None
    contact_info: Optional[str] = None
    hiring_count: Optional[int] = None
    priority: Optional[str] = None


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
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    """招聘需求分页列表"""

    total: int
    items: list[JobOut]