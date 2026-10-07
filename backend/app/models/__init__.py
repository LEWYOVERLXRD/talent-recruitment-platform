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
from app.models.candidate import Candidate, CandidateSource
from app.models.resume import Resume, ParseStatus
from app.models.recommendation import Recommendation, RecommendationStatus
from app.models.communication import Communication, CommType, CommResult
from app.models.match_analysis import MatchAnalysis

# 导出 Base（供外部使用）
from app.core.database import Base

__all__ = [
    "Base",
    "BaseModel",
    "User", "UserRole", "CompanyRole",
    "Company",
    "UserSecurityAnswer", "SecurityQuestion", "SECURITY_QUESTIONS", "SECURITY_QUESTION_COUNT",
    "Job", "JobStatus", "JobSource",
    "Candidate", "CandidateSource",
    "Resume", "ParseStatus",
    "Recommendation", "RecommendationStatus",
    "Communication", "CommType", "CommResult",
    "MatchAnalysis",
]