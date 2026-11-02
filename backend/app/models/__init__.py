"""SQLAlchemy ORM 模型汇总：导入所有模型，让 Base.metadata 能感知到所有表"""
from app.models.base import BaseModel
from app.models.user import User, UserRole, CompanyRole
from app.models.company import Company
from app.models.user_security_answer import (
    UserSecurityAnswer,
    SecurityQuestion,
    SECURITY_QUESTIONS,
    SECURITY_QUESTION_COUNT,
)
from app.models.job import Job, JobStatus, JobSource
from app.models.job_profile import JobProfile
from app.models.job_assignment import JobAssignment
from app.models.assignment_event import AssignmentEvent
from app.models.candidate import Candidate, CandidateSource
from app.models.resume import Resume, ParseStatus
from app.models.skill import Skill, ResumeSkill
from app.models.recommendation import Recommendation, RecommendationStatus
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.communication import Communication, CommType, CommResult
from app.models.match_analysis import MatchAnalysis
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.service_provider import ServiceProvider
from app.models.company_invitation import CompanyInvitation
from app.models.application import Application, ApplicationStatus, ApplicationSource, ApplicationReviewStatus, ApplicationRecordKind

# 导出 Base（供外部使用）
from app.core.database import Base

__all__ = [
    "Base",
    "BaseModel",
    "User", "UserRole", "CompanyRole",
    "Company",
    "UserSecurityAnswer", "SecurityQuestion", "SECURITY_QUESTIONS", "SECURITY_QUESTION_COUNT",
    "Job", "JobStatus", "JobSource",
    "JobProfile", "JobAssignment", "AssignmentEvent",
    "Candidate", "CandidateSource",
    "Resume", "ParseStatus",
    "Skill", "ResumeSkill",
    "Recommendation", "RecommendationStatus", "RecommendationFeedback",
    "Communication", "CommType", "CommResult",
    "MatchAnalysis",
    "Agency", "AgencyMember", "ServiceProvider", "CompanyInvitation",
    "Application", "ApplicationStatus", "ApplicationSource", "ApplicationReviewStatus", "ApplicationRecordKind",
]
