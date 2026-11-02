"""客户对固定推荐交付追加的反馈事件。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RecommendationFeedback(BaseModel):
    __tablename__ = "recommendation_feedbacks"
    __table_args__ = (
        UniqueConstraint("recommendation_id", "recommendation_version", name="uq_recommendation_feedback_version"),
        Index("ix_recommendation_feedback_time", "recommendation_id", "created_at", "id"),
    )

    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(20), nullable=False)
    conclusion: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str] = mapped_column(String(30), nullable=False)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    recommendation_version: Mapped[int] = mapped_column(Integer, nullable=False)
