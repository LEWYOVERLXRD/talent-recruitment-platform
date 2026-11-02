"""客户企业招聘员工邀请，保留邀请与处理历史。"""
from datetime import datetime

from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class CompanyInvitation(BaseModel):
    __tablename__ = "company_invitations"
    __table_args__ = (
        CheckConstraint("status IN ('pending','accepted','declined','revoked','expired')", name="ck_company_invitation_status"),
        UniqueConstraint("company_id", "user_id", "pending_key", name="uq_company_invitation_pending"),
        Index("ix_company_invitation_user_status", "user_id", "status", "expires_at"),
        Index("ix_company_invitation_company_status", "company_id", "status", "id"),
    )

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pending_key: Mapped[int | None] = mapped_column(
        Integer, Computed("CASE WHEN status='pending' THEN 1 ELSE NULL END", persisted=True)
    )
    company: Mapped["Company"] = relationship("Company")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
