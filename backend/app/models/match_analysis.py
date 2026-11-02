"""AI 匹配分析结果模型"""
from sqlalchemy import String, Text, Float, ForeignKey, Integer, JSON, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from app.models.base import BaseModel

MATCH_TEXT = Text().with_variant(MEDIUMTEXT(), "mysql")


class MatchAnalysis(BaseModel):
    """AI 匹配分析结果表：存储大语言模型的输出"""
    __tablename__ = "match_analyses"
    __table_args__ = (CheckConstraint("match_score IS NULL OR (match_score >= 0 AND match_score <= 100)", name="ck_match_score"),)

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id"), nullable=False, comment="招聘需求ID"
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id"), nullable=False, comment="候选人ID"
    )
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id"), nullable=True, comment="采用的简历版本ID"
    )
    executed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    job_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_text: Mapped[str] = mapped_column(MATCH_TEXT, nullable=True, comment="LLM 完整输出")
    extracted_skills: Mapped[str] = mapped_column(MATCH_TEXT, nullable=True, comment="抽取的技能")
    match_points: Mapped[str] = mapped_column(MATCH_TEXT, nullable=True, comment="匹配点")
    mismatch_points: Mapped[str] = mapped_column(MATCH_TEXT, nullable=True, comment="不匹配点")
    questions_to_ask: Mapped[str] = mapped_column(MATCH_TEXT, nullable=True, comment="建议追问的问题")
    model_used: Mapped[str] = mapped_column(String(100), nullable=True, comment="使用的模型名称")
    match_score: Mapped[float] = mapped_column(
        Float, nullable=True, comment="匹配得分(可选，0-100)"
    )
