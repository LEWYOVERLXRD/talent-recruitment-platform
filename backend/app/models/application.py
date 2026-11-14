"""求职者投递记录：与猎头推荐记录分离，保留求职者可见的状态。"""
from datetime import datetime
import enum

from sqlalchemy import Computed, DateTime, ForeignKey, String, Text, UniqueConstraint, Index, CheckConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ApplicationStatus(str, enum.Enum):
    submitted = "submitted"
    screening = "screening"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"


class ApplicationSource(str, enum.Enum):
    self_apply = "self_apply"
    hunter_referral = "hunter_referral"


class ApplicationReviewStatus(str, enum.Enum):
    pending = "pending"
    not_recommended = "not_recommended"
    recommendation_draft = "recommendation_draft"
    recommended = "recommended"
    legacy_unrouted = "legacy_unrouted"


class ApplicationRecordKind(str, enum.Enum):
    primary = "primary"
    duplicate = "duplicate"


class Application(BaseModel):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", "publisher_user_id", name="uq_application_job_candidate_publisher"),
        UniqueConstraint("primary_slot", name="uq_application_primary_slot"),
        CheckConstraint("record_kind IN ('primary', 'duplicate')", name="ck_application_record_kind"),
        CheckConstraint(
            "review_status IN ('pending','not_recommended','recommendation_draft','recommended','legacy_unrouted')",
            name="ck_application_review_status",
        ),
        CheckConstraint("source IN ('self_apply', 'hunter_referral')", name="ck_application_source"),
        CheckConstraint("status IN ('submitted', 'screening', 'interview', 'offer', 'rejected', 'withdrawn')", name="ck_application_status"),
        Index("ix_application_applicant_status", "applicant_user_id", "status", "id"),
        Index("ix_application_job_status", "job_id", "status", "id"),
        Index("ix_application_publisher_review", "publisher_user_id", "review_status", "id"),
        Index("ix_application_canonical", "canonical_application_id", "id"),
    )

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), nullable=False)
    applicant_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("job_assignments.id"), nullable=True,
                                                       comment="求职者选择的有效承接")
    working_candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id"), nullable=True,
                                                              comment="投递后生成的猎头工作候选人")
    working_resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id"), nullable=True,
                                                           comment="猎头工作候选人的固定简历")
    source: Mapped[ApplicationSource] = mapped_column(
        SAEnum(ApplicationSource), nullable=False, default=ApplicationSource.self_apply
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        SAEnum(ApplicationStatus), nullable=False, default=ApplicationStatus.submitted
    )
    publisher_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="发布该岗位的猎头账号ID"
    )
    record_kind: Mapped[ApplicationRecordKind] = mapped_column(
        SAEnum(ApplicationRecordKind), nullable=False, default=ApplicationRecordKind.primary,
        comment="主投递或重复投递记录"
    )
    canonical_application_id: Mapped[int | None] = mapped_column(
        ForeignKey("applications.id"), nullable=True, comment="对应的岗位候选人主投递"
    )
    primary_slot: Mapped[str | None] = mapped_column(
        String(80),
        Computed(
            "CASE WHEN record_kind = 'primary' THEN CONCAT(job_id, ':', candidate_id) ELSE NULL END",
            persisted=True,
        ),
        nullable=True,
    )
    review_status: Mapped[ApplicationReviewStatus] = mapped_column(
        SAEnum(ApplicationReviewStatus), nullable=False, default=ApplicationReviewStatus.pending,
        comment="猎头审核状态"
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="猎头内部审核备注")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, comment="最近审核人ID")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近审核时间")
    rejection_reason_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rejection_reason_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
