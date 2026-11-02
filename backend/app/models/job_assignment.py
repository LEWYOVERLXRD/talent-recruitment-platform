"""客户定向授权后的需求承接主记录。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class JobAssignment(BaseModel):
    __tablename__ = "job_assignments"
    __table_args__ = (
        UniqueConstraint("job_id", "provider_id", name="uq_job_assignment_job_provider"),
        CheckConstraint(
            "status IN ('invited','active','declined','cancelled','completed')",
            name="ck_job_assignment_status",
        ),
        CheckConstraint(
            "owner_user_id IS NULL OR owner_user_id > 0",
            name="ck_job_assignment_owner",
        ),
        CheckConstraint("job_version > 0", name="ck_job_assignment_version"),
        CheckConstraint("round_no > 0", name="ck_job_assignment_round"),
        Index("ix_job_assignment_provider_status", "provider_id", "status"),
        Index("ix_job_assignment_job_status", "job_id", "status"),
    )

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    provider_id: Mapped[int] = mapped_column(ForeignKey("service_providers.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="invited", server_default="invited")
    job_version: Mapped[int] = mapped_column(Integer, nullable=False, comment="本轮授权对应的需求版本")
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    job_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, comment="安全岗位快照")
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="机构任务当前负责人"
    )
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    invited_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ended_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
