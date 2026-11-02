"""机构 API 白名单，不返回密码、密保和私有联系方式。"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgencyCreate(Input):
    name: str = Field(min_length=1, max_length=100)
    manager_user_id: int = Field(gt=0)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("机构名称不能为空")
        return value


class AgencyStatusUpdate(Input):
    status: Literal["active", "disabled"]


class MemberInvite(Input):
    username: str = Field(min_length=1, max_length=50)
    role: Literal["manager", "staff"] = "staff"


class InvitationDecision(Input):
    accept: bool


class MemberRoleUpdate(Input):
    role: Literal["manager", "staff"]


class MemberLeave(Input):
    transfer_to_user_id: int | None = Field(None, gt=0)


class AgencyOut(BaseModel):
    id: int
    name: str
    status: str
    model_config = ConfigDict(from_attributes=True)


class MemberOut(BaseModel):
    id: int
    agency_id: int
    user_id: int
    role: str
    status: str
    username: str | None = None
    real_name: str | None = None
    enabled: bool | None = None
    joined_at: datetime | None = None
    left_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class AgencyContext(BaseModel):
    agency: AgencyOut | None = None
    membership: MemberOut | None = None
    invitations: list[MemberOut]


class AgencyList(BaseModel):
    total: int
    items: list[AgencyOut]
