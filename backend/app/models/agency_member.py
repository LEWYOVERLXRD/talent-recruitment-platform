"""保留加入退出历史，以生成列唯一约束保护有效成员身份。"""
from datetime import datetime

from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AgencyMember(BaseModel):
    __tablename__ = "agency_members"
    __table_args__ = (
        CheckConstraint("role IN ('manager','staff')", name="ck_agency_member_role"),
        CheckConstraint("status IN ('invited','active','declined','cancelled','left')", name="ck_agency_member_status"),
        UniqueConstraint("active_user_id", name="uq_agency_member_active_user"),
        UniqueConstraint("agency_id", "user_id", "pending_key", name="uq_agency_member_pending"),
        Index("ix_agency_member_lookup", "agency_id", "user_id", "status"),
    )

    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="staff")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="invited")
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    left_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active_user_id: Mapped[int | None] = mapped_column(
        Integer, Computed("CASE WHEN status='active' THEN user_id ELSE NULL END", persisted=True)
    )
    pending_key: Mapped[int | None] = mapped_column(
        Integer, Computed("CASE WHEN status='invited' THEN 1 ELSE NULL END", persisted=True)
    )
