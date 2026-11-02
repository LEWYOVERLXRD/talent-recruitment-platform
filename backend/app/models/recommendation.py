"""推荐记录模型（方案B：猎头核心）

原 Application（求职投递）在方案B中正式正名为“推荐/交付记录”：
记录猎头将候选人推荐给客户企业后，该候选人在某招聘需求下的全流程状态。
"""
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, UniqueConstraint, Enum as SAEnum, JSON, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.models.base import BaseModel


class RecommendationStatus(str, enum.Enum):
    """候选人在某招聘需求下的推荐/交付状态（对齐猎头交付语言）"""
    pending_contact = "pending_contact"      # 待沟通
    contacted = "contacted"                  # 已沟通
    pending_recommend = "pending_recommend"  # 待推荐
    recommended = "recommended"              # 已推荐
    accepted = "accepted"                    # 客户已接收
    interviewing = "interviewing"            # 面试中
    passed = "passed"                        # 已通过
    rejected = "rejected"                    # 已拒收


class Recommendation(BaseModel):
    """推荐记录表：猎头→候选人+招聘需求的交付状态单"""
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("assignment_id", "candidate_id", name="uq_recommend_assignment_candidate"),
        UniqueConstraint("application_id", name="uq_recommendation_application"),
        CheckConstraint("version > 0", name="ck_recommendation_version"),
        Index("ix_recommend_assignment_status", "assignment_id", "status", "id"),
        Index("ix_recommend_job_status", "job_id", "status", "id"),
    )

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id"), nullable=False, comment="招聘需求ID"
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id"), nullable=False, comment="候选人ID"
    )
    assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_assignments.id"), nullable=True, comment="需求承接ID；历史记录可空"
    )
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("applications.id"), nullable=True, comment="来源求职投递ID"
    )
    assignment_round: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="绑定承接轮次")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, comment="草稿创建人")
    preparation_communication_id: Mapped[int | None] = mapped_column(
        ForeignKey("communications.id"), nullable=True, comment="内部准备沟通依据"
    )
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id"), nullable=True, comment="选定简历版本")
    job_version: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="绑定需求版本")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1", comment="乐观锁版本")
    recommendation_note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="猎头推荐说明")
    delivery_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="客户可见的固定交付快照")
    share_basis: Mapped[str | None] = mapped_column(Text, nullable=True, comment="内部记录的材料共享依据")
    share_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="实际共享确认时间")
    share_recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, comment="共享依据记录人")
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
