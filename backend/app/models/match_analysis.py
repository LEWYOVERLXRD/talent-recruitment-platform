"""AI 匹配分析结果模型"""
from sqlalchemy import String, Text, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class MatchAnalysis(BaseModel):
    """AI 匹配分析结果表：存储大语言模型的输出"""
    __tablename__ = "match_analyses"

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id"), nullable=False, comment="招聘需求ID"
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id"), nullable=False, comment="候选人ID"
    )
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id"), nullable=True, comment="采用的简历版本ID"
    )
    analysis_text: Mapped[str] = mapped_column(Text, nullable=True, comment="LLM 完整输出")
    extracted_skills: Mapped[str] = mapped_column(Text, nullable=True, comment="抽取的技能")
    match_points: Mapped[str] = mapped_column(Text, nullable=True, comment="匹配点")
    mismatch_points: Mapped[str] = mapped_column(Text, nullable=True, comment="不匹配点")
    questions_to_ask: Mapped[str] = mapped_column(Text, nullable=True, comment="建议追问的问题")
    model_used: Mapped[str] = mapped_column(String(100), nullable=True, comment="使用的模型名称")
    match_score: Mapped[float] = mapped_column(
        Float, nullable=True, comment="匹配得分(可选，0-100)"
    )
