"""求职者可投递的有效承接；不暴露客户联系人或内部邀请历史。"""
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import aliased

from app.models import Agency, AgencyMember, Job, JobAssignment, JobStatus, ServiceProvider, User, UserRole


def receiving_scope():
    owner = aliased(User)
    active_member = exists(select(AgencyMember.id).where(
        AgencyMember.user_id == owner.id, AgencyMember.agency_id == ServiceProvider.agency_id,
        AgencyMember.status == "active",
    ).correlate(owner, ServiceProvider))
    independent = ~exists(select(AgencyMember.id).where(
        AgencyMember.user_id == owner.id, AgencyMember.status == "active",
    ).correlate(owner))
    active_agency = exists(select(Agency.id).where(
        Agency.id == ServiceProvider.agency_id, Agency.status == "active",
    ).correlate(ServiceProvider))
    return and_(
        Job.status == JobStatus.open, Job.confirmed_at.is_not(None), Job.confirmed_by.is_not(None),
        JobAssignment.job_id == Job.id, JobAssignment.status == "active",
        JobAssignment.job_version == Job.version, JobAssignment.provider_id == ServiceProvider.id,
        exists(select(owner.id).where(
            owner.id == JobAssignment.owner_user_id, owner.enabled.is_(True), owner.role == UserRole.headhunter,
            or_(and_(ServiceProvider.kind == "individual", ServiceProvider.user_id == owner.id, independent),
                and_(ServiceProvider.kind == "agency", active_agency, active_member)),
        ).correlate(JobAssignment, ServiceProvider)),
    )


def public_job_scope():
    return exists(select(JobAssignment.id).join(ServiceProvider, ServiceProvider.id == JobAssignment.provider_id)
                  .where(receiving_scope()).correlate(Job))


def receiving_assignments(db, job_id):
    return db.query(JobAssignment).join(Job, Job.id == JobAssignment.job_id).join(
        ServiceProvider, ServiceProvider.id == JobAssignment.provider_id
    ).filter(Job.id == job_id, receiving_scope()).order_by(JobAssignment.id).all()


def public_receivers(db, job_id):
    result = []
    for assignment in receiving_assignments(db, job_id):
        owner = db.get(User, assignment.owner_user_id)
        provider = db.get(ServiceProvider, assignment.provider_id)
        agency = db.get(Agency, provider.agency_id) if provider.kind == "agency" else None
        result.append({
            "assignment_id": assignment.id, "headhunter_name": owner.real_name or owner.username,
            "provider_name": agency.name if agency else owner.real_name or owner.username,
            "provider_kind": provider.kind,
        })
    return result
