"""需求承接状态的追加式审计事件。"""
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AssignmentEvent(BaseModel):
    __tablename__ = "assignment_events"
    __table_args__ = (
        CheckConstraint("job_version > 0", name="ck_assignment_event_version"),
        Index("ix_assignment_event_assignment_time", "assignment_id", "created_at", "id"),
    )

    assignment_id: Mapped[int] = mapped_column(ForeignKey("job_assignments.id"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    job_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
