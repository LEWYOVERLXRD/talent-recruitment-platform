"""企业面试题生成题组模型"""
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class InterviewQuestionSet(BaseModel):
    """企业面试题组表：记录基于固定交付快照生成的结构化面试题及输入/模型溯源"""
    __tablename__ = "interview_question_sets"
    __table_args__ = (
        CheckConstraint(
            "recommendation_status IN ('accepted', 'interviewing')",
            name="ck_iqs_rec_status",
        ),
        CheckConstraint("recommendation_version > 0", name="ck_iqs_rec_version"),
        Index("ix_iqs_recommendation_created", "recommendation_id", "created_at", "id"),
    )

    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id"), nullable=False, comment="来源推荐ID"
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id"), nullable=False, comment="招聘需求ID"
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id"), nullable=False, comment="候选人ID"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="生成操作人ID"
    )
    recommendation_version: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="生成时的推荐版本号"
    )
    recommendation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="生成时的推荐状态"
    )
    model_used: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="实际使用的模型名称"
    )
    input_summary: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="脱敏后的固定输入摘要"
    )
    questions: Mapped[list] = mapped_column(
        JSON, nullable=False, comment="结构化面试题数组"
    )
