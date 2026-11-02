"""企业相关 Pydantic 数据模型"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import CompanyRole


class CompanyOut(BaseModel):
    """企业信息响应"""
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class CompanyAdminSummary(BaseModel):
    """管理员企业摘要：成员数包含禁用账号，仅统计企业招聘方。"""
    id: int
    name: str
    created_at: datetime
    member_count: int
    manager_count: int
    enabled_manager_count: int

    model_config = ConfigDict(from_attributes=True)


class CompanyAdminPage(BaseModel):
    total: int
    items: list[CompanyAdminSummary]


class CompanyAdminMember(BaseModel):
    """平台只读成员字段，不包含联系方式或认证凭据。"""
    id: int
    username: str
    real_name: Optional[str] = None
    company_role: Optional[CompanyRole] = None
    enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanyAdminMemberPage(BaseModel):
    total: int
    items: list[CompanyAdminMember]


class CompanyMemberOut(BaseModel):
    """企业成员信息（对外不返回密码等敏感字段）"""
    id: int
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_role: Optional[CompanyRole] = None
    enabled: bool = True
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CompanyMemberUpdateIn(BaseModel):
    """调整成员在企业内的角色"""
    company_role: CompanyRole = Field(..., description="manager=管理者，staff=普通员工")


class CompanyInvitationCreateIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)


class CompanyInvitationDecisionIn(BaseModel):
    accept: bool


class CompanyInvitationOut(BaseModel):
    id: int
    company_id: int
    company_name: str
    user_id: int
    username: str
    real_name: Optional[str] = None
    invited_by: int
    status: str
    expires_at: datetime
    decided_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
