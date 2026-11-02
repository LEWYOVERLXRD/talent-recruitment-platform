"""招聘需求、任务与匹配共享的 SQL 权限条件。"""
from sqlalchemy import and_, exists, false, or_, select, true

from app.models import Agency, AgencyMember, Candidate, Job, JobAssignment, JobStatus, ServiceProvider, UserRole


def provider_scope(user, *, owner=None, managers_only=False):
    independent = ~exists(select(AgencyMember.id).where(
        AgencyMember.user_id == user.id, AgencyMember.status == "active",
    ))
    individual = and_(ServiceProvider.kind == "individual",
                      ServiceProvider.user_id == user.id, independent)
    if owner is not None and not managers_only:
        individual = and_(individual, owner == user.id)
    member_conditions = [AgencyMember.agency_id == Agency.id,
                         AgencyMember.user_id == user.id, AgencyMember.status == "active"]
    if managers_only or owner is None:
        member_conditions.append(AgencyMember.role == "manager")
    else:
        member_conditions.append(or_(AgencyMember.role == "manager", owner == user.id))
    agency = and_(ServiceProvider.kind == "agency", exists(select(Agency.id).where(
        Agency.id == ServiceProvider.agency_id, Agency.status == "active",
        exists(select(AgencyMember.id).where(*member_conditions).correlate(Agency, JobAssignment)),
    ).correlate(ServiceProvider, JobAssignment)))
    return or_(individual, agency)


def active_assignment_scope(user, *, same_candidate=False):
    conditions = [JobAssignment.job_id == Job.id, JobAssignment.status == "active",
                  JobAssignment.job_version == Job.version,
                  JobAssignment.provider_id == ServiceProvider.id,
                  provider_scope(user, owner=JobAssignment.owner_user_id)]
    if same_candidate:
        conditions.append(JobAssignment.provider_id == Candidate.provider_id)
    return exists(select(JobAssignment.id).select_from(JobAssignment).join(
        ServiceProvider, ServiceProvider.id == JobAssignment.provider_id
    ).where(*conditions).correlate(Job, Candidate))


def task_visibility(user, *, same_candidate=False):
    if not user.enabled:
        return false()
    if user.role == UserRole.admin:
        return true()
    if user.role != UserRole.headhunter:
        return false()
    return and_(Job.status != JobStatus.closed, Job.confirmed_at.is_not(None),
                Job.confirmed_by.is_not(None), active_assignment_scope(user, same_candidate=same_candidate))


def invitation_visibility(user):
    if not user.enabled or user.role != UserRole.headhunter:
        return false()
    invited = exists(select(JobAssignment.id).select_from(JobAssignment).join(
        ServiceProvider, ServiceProvider.id == JobAssignment.provider_id
    ).where(
        JobAssignment.job_id == Job.id, JobAssignment.status == "invited",
        JobAssignment.job_version == Job.version,
        provider_scope(user),
    ).correlate(Job))
    return and_(Job.status == JobStatus.open, Job.confirmed_at.is_not(None), invited)


def job_visibility(user):
    if not user.enabled:
        return false()
    if user.role == UserRole.admin:
        return true()
    if user.role == UserRole.recruiter:
        return Job.client_company_id == user.company_id if user.company_id else false()
    if user.role != UserRole.headhunter:
        return false()
    return or_(and_(Job.created_by == user.id, Job.ever_confirmed_at.is_(None)),
               task_visibility(user), invitation_visibility(user))


def assignment_visibility(user):
    if not user.enabled:
        return false()
    if user.role == UserRole.admin:
        return true()
    if user.role == UserRole.recruiter:
        return Job.client_company_id == user.company_id if user.company_id else false()
    if user.role != UserRole.headhunter:
        return false()
    supervisor = provider_scope(user, managers_only=True)
    assigned = and_(JobAssignment.status == "active", Job.status != JobStatus.closed,
                    Job.confirmed_at.is_not(None), JobAssignment.job_version == Job.version,
                    JobAssignment.owner_user_id == user.id,
                    provider_scope(user, owner=JobAssignment.owner_user_id))
    return and_(JobAssignment.provider_id == ServiceProvider.id, or_(supervisor, assigned))
