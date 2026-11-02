"""客户定向需求邀请及承接操作的输入、输出白名单。"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderOption(BaseModel):
    kind: Literal["individual", "agency"]
    target_id: int
    display_name: str


class InvitationCreate(Input):
    provider_kind: Literal["individual", "agency"]
    target_id: int = Field(gt=0)
    expected_version: int = Field(gt=0)


class AssignmentAction(Input):
    expected_round: int = Field(ge=1)
    reason: str | None = Field(None, max_length=1000)


class AssignmentTransfer(Input):
    expected_round: int = Field(ge=1)
    expected_owner_user_id: int | None = Field(None, gt=0)
    owner_user_id: int = Field(gt=0)


class AssignmentListItem(BaseModel):
    id: int
    job_id: int
    job_title: str | None = None
    client_company_name: str | None = None
    provider_id: int
    provider_name: str | None = None
    provider_kind: Literal["individual", "agency"]
    status: str
    job_version: int
    round_no: int
    job_snapshot: dict
    owner_user_id: int | None = None
    invited_at: datetime
    accepted_at: datetime | None = None
    ended_at: datetime | None = None
    end_reason: str | None = None
    has_current_authorization: bool = False
    contact_person: str | None = None
    contact_info: str | None = None


class AssignmentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_id: int
    event_type: str
    from_status: str | None = None
    to_status: str
    job_version: int
    reason: str | None = None
    payload: dict | None = None
    created_at: datetime


class AssignmentPage(BaseModel):
    total: int
    items: list[AssignmentListItem]
