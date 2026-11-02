"""列表、计数、详情共用 SQL 权限条件，不按历史建档人继续授权。"""
from sqlalchemy import and_, exists, false, or_, select, true
from sqlalchemy.orm import Session

from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.candidate import Candidate
from app.models.service_provider import ServiceProvider
from app.models.user import User, UserRole


def candidate_visibility(user: User):
    if not user.enabled:
        return false()
    if user.role == UserRole.admin:
        return true()
    if user.role == UserRole.jobseeker:
        return Candidate.candidate_user_id == user.id
    if user.role != UserRole.headhunter:
        return false()
    return exists(select(ServiceProvider.id).where(
        ServiceProvider.id == Candidate.provider_id,
        or_(
            and_(ServiceProvider.kind == "individual", ServiceProvider.user_id == user.id,
                 Candidate.owner_user_id == user.id),
            and_(ServiceProvider.kind == "agency", exists(select(Agency.id).where(
                Agency.id == ServiceProvider.agency_id, Agency.status == "active",
                exists(select(AgencyMember.id).where(
                    AgencyMember.agency_id == Agency.id, AgencyMember.user_id == user.id,
                    AgencyMember.status == "active",
                    or_(AgencyMember.role == "manager", Candidate.owner_user_id == user.id),
                ).correlate(Agency, Candidate)),
            ).correlate(ServiceProvider, Candidate))),
        ),
    ).correlate(Candidate))


def can_access_candidate(db: Session, user: User, candidate: Candidate) -> bool:
    return db.query(Candidate.id).filter(
        Candidate.id == candidate.id, candidate_visibility(user)
    ).first() is not None
