"""生成招聘需求所依据的岗位原始资料。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class JobProfile(BaseModel):
    __tablename__ = "job_profiles"
    __table_args__ = (
        CheckConstraint("source_type IN ('manual','client_provided','headhunter_collected','legacy_backfill')",
                        name="ck_job_profile_source"),
        CheckConstraint("version > 0", name="ck_job_profile_version"),
    )

    raw_content: Mapped[str] = mapped_column(Text, nullable=False, comment="原始岗位资料")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="资料来源")
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1", comment="资料版本"
    )
    submitted_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="资料提交人"
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="资料提交时间"
    )
