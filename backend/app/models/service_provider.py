"""统一个人猎头和猎头机构的资产、承接主体。"""
from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ServiceProvider(BaseModel):
    __tablename__ = "service_providers"
    __table_args__ = (
        CheckConstraint(
            "(kind='individual' AND user_id IS NOT NULL AND agency_id IS NULL) OR "
            "(kind='agency' AND agency_id IS NOT NULL AND user_id IS NULL)",
            name="ck_service_provider_identity",
        ),
    )

    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)
    agency_id: Mapped[int | None] = mapped_column(ForeignKey("agencies.id"), unique=True, nullable=True)
