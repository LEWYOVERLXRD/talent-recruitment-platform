"""猎头机构，与客户企业分开。"""
from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Agency(BaseModel):
    __tablename__ = "agencies"
    __table_args__ = (CheckConstraint("status IN ('active','disabled')", name="ck_agency_status"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
