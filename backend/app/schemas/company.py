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