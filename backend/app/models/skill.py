"""标准技能与具体简历版本的带证据关联。"""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Skill(BaseModel):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100).with_variant(String(100, collation="utf8mb4_bin"), "mysql"), nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)


class ResumeSkill(BaseModel):
    __tablename__ = "resume_skills"
    __table_args__ = (
        UniqueConstraint("resume_id", "skill_id", name="uq_resume_skill"),
        CheckConstraint("review_status IN ('unreviewed','confirmed','rejected')", name="ck_skill_review"),
        CheckConstraint("(reviewed_by IS NULL AND reviewed_at IS NULL) OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)", name="ck_skill_reviewer_pair"),
    )

    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), nullable=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unreviewed")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
