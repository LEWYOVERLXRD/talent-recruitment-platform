"""推荐记录模型（方案B：猎头核心）

原 Application（求职投递）在方案B中正式正名为“推荐/交付记录”：
记录猎头将候选人推荐给客户企业后，该候选人在某招聘需求下的全流程状态。
"""
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, UniqueConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.models.base import BaseModel


class RecommendationStatus(str, enum.Enum):
    """候选人在某招聘需求下的推荐/交付状态（对齐猎头交付语言）"""
    pending_contact = "pending_contact"      # 待沟通
    contacted = "contacted"                  # 已沟通
    pending_recommend = "pending_recommend"  # 待推荐
    recommended = "recommended"              # 已推荐
    interviewing = "interviewing"            # 面试中
    passed = "passed"                        # 已通过
    rejected = "rejected"                    # 已拒收


class Recommendation(BaseModel):
    """推荐记录表：猎头→候选人+招聘需求的交付状态单"""
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_recommend_job_candidate"),
    )

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id"), nullable=False, comment="招聘需求ID"
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id"), nullable=False, comment="候选人ID"
    )
    status: Mapped[RecommendationStatus] = mapped_column(
        SAEnum(RecommendationStatus), nullable=False,
        default=RecommendationStatus.pending_contact, comment="交付状态"
    )
    recommended_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="推荐人(猎头)ID"
    )
    recommended_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, comment="推荐时间"
    )
    reject_reason: Mapped[str] = mapped_column(
        Text, nullable=True, comment="企业拒收原因(拒收时必填)"
    )
    client_feedback: Mapped[str] = mapped_column(
        Text, nullable=True, comment="客户企业反馈"
    )
    interview_feedback: Mapped[str] = mapped_column(
        Text, nullable=True, comment="面试反馈"
    )