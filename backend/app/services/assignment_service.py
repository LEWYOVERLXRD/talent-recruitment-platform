"""定向邀请、双向承接确认和机构任务分配。"""
from datetime import datetime
from functools import wraps

from fastapi import HTTPException
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.crud.job_assignment import add_event, events_for_assignment
from app.models import Agency, AgencyMember, AssignmentEvent, CompanyRole, Job, JobAssignment, JobStatus, ServiceProvider, User, UserRole
from app.schemas.job_assignment import AssignmentEventOut, AssignmentListItem, ProviderOption
from app.services.job_access import assignment_visibility
from app.services.job_locks import lock_context


def mutation(function):
    @wraps(function)
    def wrapped(db, *args, **kwargs):
        try:
            return function(db, *args, **kwargs)
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "承接数据已发生变化，请刷新后重试") from None
        except Exception:
            db.rollback()
            raise
    return wrapped


def _require_client_manager(user, job):
    if user.role != UserRole.recruiter or user.company_role != CompanyRole.manager or user.company_id != job.client_company_id:
        raise HTTPException(403, "需要本客户企业主管权限")


def _provider(db, kind, target_id):
    query = db.query(ServiceProvider).filter(ServiceProvider.kind == kind)
    if kind == "individual":
        query = query.filter(ServiceProvider.user_id == target_id)
    else:
        query = query.filter(ServiceProvider.agency_id == target_id)
    return query.first()


def _provider_active(db, provider, users=None):
    if provider.kind == "individual":
        hunter = (users or {}).get(provider.user_id) or db.get(User, provider.user_id)
        if hunter is None or not hunter.enabled or hunter.role != UserRole.headhunter:
            return False
        return not db.query(AgencyMember.id).filter(
            AgencyMember.user_id == hunter.id, AgencyMember.status == "active"
        ).with_for_update().first()
    agency = db.get(Agency, provider.agency_id)
    return bool(agency and agency.status == "active")


def _active_manager(db, user_id, agency_id, *, users=None):
    member = db.query(AgencyMember).filter(
        AgencyMember.user_id == user_id, AgencyMember.agency_id == agency_id,
        AgencyMember.role == "manager", AgencyMember.status == "active",
    ).populate_existing().with_for_update().first()
    user = (users or {}).get(user_id) or db.get(User, user_id)
    return bool(member and user and user.enabled and user.role == UserRole.headhunter)


def _active_member(db, user_id, agency_id, *, users=None):
    member = db.query(AgencyMember).filter(
        AgencyMember.user_id == user_id, AgencyMember.agency_id == agency_id,
        AgencyMember.status == "active",
    ).populate_existing().with_for_update().first()
    user = (users or {}).get(user_id) or db.get(User, user_id)
    return bool(member and user and user.enabled and user.role == UserRole.headhunter)


def _require_provider_operator(db, user, provider, *, users=None):
    if user.role != UserRole.headhunter or not user.enabled:
        raise HTTPException(403, "需要启用的猎头账号")
    if provider.kind == "individual":
        if provider.user_id != user.id or db.query(AgencyMember.id).filter(
            AgencyMember.user_id == user.id, AgencyMember.status == "active"
        ).populate_existing().with_for_update().first():
            raise HTTPException(403, "只能由受邀的独立猎头本人处理")
        return
    agency = db.get(Agency, provider.agency_id)
    if not agency or agency.status != "active" or not _active_manager(
        db, user.id, agency.id, users=users
    ):
        raise HTTPException(403, "仅受邀机构的有效主管可以处理承接")


def _snapshot(job):
    return {
        "version": job.version, "title": job.title, "department": job.department,
        "description": job.description, "requirements": job.requirements,
        "salary_min": job.salary_min, "salary_max": job.salary_max,
        "location": job.location, "hiring_count": job.hiring_count,
    }


def _assignment_view(db, user, assignment):
    job = db.get(Job, assignment.job_id)
    provider = db.get(ServiceProvider, assignment.provider_id)
    subject = db.get(Agency, provider.agency_id) if provider.kind == "agency" else db.get(User, provider.user_id)
    provider_name = (subject.name if provider.kind == "agency" else subject.real_name or subject.username) if subject else None
    contact_allowed = bool(
        user.role == UserRole.admin or
        (user.role == UserRole.recruiter and user.company_id == job.client_company_id) or
        (assignment.status == "active" and assignment.job_version == job.version and
         job.confirmed_at is not None and job.status != JobStatus.closed and
         _can_view_provider_assignment(db, user, assignment))
    )
    return AssignmentListItem(
        id=assignment.id, job_id=assignment.job_id, provider_id=assignment.provider_id,
        job_title=job.title, client_company_name=job.client_company_name,
        provider_name=provider_name, provider_kind=provider.kind,
        status=assignment.status, job_version=assignment.job_version,
        round_no=assignment.round_no, job_snapshot=assignment.job_snapshot,
        owner_user_id=assignment.owner_user_id, invited_at=assignment.invited_at,
        accepted_at=assignment.accepted_at, ended_at=assignment.ended_at,
        end_reason=assignment.end_reason,
        has_current_authorization=(assignment.status == "active" and
                                   assignment.job_version == job.version and
                                   job.confirmed_at is not None and job.status != JobStatus.closed),
        contact_person=job.contact_person if contact_allowed else None,
        contact_info=job.contact_info if contact_allowed else None,
    )


def _can_view_provider_assignment(db, user, assignment):
    provider = db.get(ServiceProvider, assignment.provider_id)
    if provider is None or not user.enabled:
        return False
    if provider.kind == "individual":
        return (provider.user_id == user.id and
                not db.query(AgencyMember.id).filter(
                    AgencyMember.user_id == user.id, AgencyMember.status == "active"
                ).first())
    agency = db.get(Agency, provider.agency_id)
    if not agency or agency.status != "active":
        return False
    member = db.query(AgencyMember).filter(
        AgencyMember.user_id == user.id, AgencyMember.agency_id == agency.id,
        AgencyMember.status == "active",
    ).first()
    job = db.get(Job, assignment.job_id)
    return bool(member and (member.role == "manager" or
                            (assignment.status == "active" and assignment.owner_user_id == user.id and
                             job.status != JobStatus.closed and job.confirmed_at is not None and
                             assignment.job_version == job.version)))


def provider_options(db: Session, user: User):
    if not user.enabled or user.role != UserRole.recruiter or user.company_id is None or user.company_role != CompanyRole.manager:
        raise HTTPException(403, "只有已归属企业的招聘方可以选择承接主体")
    result = []
    agencies = db.query(Agency, ServiceProvider.id).join(
        ServiceProvider, ServiceProvider.agency_id == Agency.id
    ).filter(Agency.status == "active", ServiceProvider.kind == "agency").order_by(Agency.id).all()
    for agency, _ in agencies:
        result.append(ProviderOption(kind="agency", target_id=agency.id, display_name=agency.name))
    hunters = db.query(User).filter(User.role == UserRole.headhunter, User.enabled.is_(True)).order_by(User.id).all()
    for hunter in hunters:
        if db.query(AgencyMember.id).filter(
            AgencyMember.user_id == hunter.id, AgencyMember.status == "active"
        ).with_for_update().first():
            continue
        result.append(ProviderOption(kind="individual", target_id=hunter.id,
                                     display_name=hunter.real_name or hunter.username))
    return result


@mutation
def invite_provider(db: Session, user: User, job_id: int, kind: str,
                    target_id: int, expected_version: int):
    probe = _provider(db, kind, target_id)
    if probe is None:
        if kind != "individual" or db.get(User, target_id) is None:
            raise HTTPException(404, "服务主体不存在")
        probe = ServiceProvider(kind=kind, user_id=target_id)
        db.add(probe)
        db.flush()
    actor, job, assignments, users, agencies = lock_context(
        db, user.id, job_id, provider_ids=[probe.id],
        user_ids=[probe.user_id] if probe.user_id else (),
    )
    _require_client_manager(actor, job)
    if job.status != JobStatus.open or job.version != expected_version or job.confirmed_at is None:
        raise HTTPException(409, "需求未开放、未确认或版本已变化")
    provider = db.query(ServiceProvider).filter(ServiceProvider.id == probe.id).populate_existing().first()
    if provider is None or not _provider_active(db, provider, users):
        raise HTTPException(409, "目标猎头或机构当前不可承接")
    assignment = next((row for row in assignments if row.provider_id == provider.id), None)
    now = datetime.now()
    if assignment is None:
        assignment = JobAssignment(
            job_id=job.id, provider_id=provider.id, status="invited", job_version=job.version,
            round_no=1, job_snapshot=_snapshot(job), invited_by=actor.id, invited_at=now,
        )
        db.add(assignment)
        db.flush()
        add_event(db, assignment=assignment, actor_id=actor.id,
                  event_type="invited", old_status=None, payload={"round": 1})
    elif assignment.status == "invited" and assignment.job_version == job.version:
        raise HTTPException(409, "该主体已有待处理的当前版本邀请")
    elif assignment.status == "active" and assignment.job_version == job.version:
        raise HTTPException(409, "该主体已承接当前版本需求")
    else:
        previous = {
            "status": assignment.status, "job_version": assignment.job_version,
            "round_no": assignment.round_no, "job_snapshot": assignment.job_snapshot,
            "owner_user_id": assignment.owner_user_id,
            "invited_by": assignment.invited_by, "invited_at": assignment.invited_at.isoformat(),
            "accepted_by": assignment.accepted_by,
            "accepted_at": assignment.accepted_at.isoformat() if assignment.accepted_at else None,
            "ended_by": assignment.ended_by, "ended_at": assignment.ended_at.isoformat() if assignment.ended_at else None,
            "end_reason": assignment.end_reason,
        }
        old = assignment.status
        assignment.status, assignment.job_version = "invited", job.version
        assignment.round_no += 1
        assignment.job_snapshot = _snapshot(job)
        assignment.invited_by, assignment.invited_at = actor.id, now
        assignment.owner_user_id = assignment.accepted_by = assignment.accepted_at = None
        assignment.ended_by = assignment.ended_at = assignment.end_reason = None
        add_event(db, assignment=assignment, actor_id=actor.id, event_type="invited",
                  old_status=old, payload={"round": assignment.round_no, "previous_round": previous})
    db.commit()
    db.refresh(assignment)
    return _assignment_view(db, actor, assignment)


def _get_assignment(db, assignment_id, *, lock=False):
    q = db.query(JobAssignment).filter(JobAssignment.id == assignment_id)
    if lock:
        q = q.populate_existing().with_for_update()
    assignment = q.first()
    if assignment is None:
        raise HTTPException(404, "承接记录不存在或无权访问")
    return assignment


def _require_visible(db, user, assignment):
    if not user.enabled:
        raise HTTPException(403, "账号已停用")
    job = db.get(Job, assignment.job_id)
    if user.role == UserRole.admin:
        return job
    if user.role == UserRole.recruiter and user.company_id == job.client_company_id:
        return job
    if user.role == UserRole.headhunter and _can_view_provider_assignment(db, user, assignment):
        return job
    raise HTTPException(404, "承接记录不存在或无权访问")


@mutation
def decide_invitation(db: Session, user: User, assignment_id: int, *,
                      expected_round: int, accept: bool, reason: str | None = None):
    probe = _get_assignment(db, assignment_id)
    actor, job, assignments, users, agencies = lock_context(
        db, user.id, probe.job_id, provider_ids=[probe.provider_id],
    )
    assignment = next((row for row in assignments if row.id == assignment_id), None)
    if assignment is None:
        raise HTTPException(404, "承接记录不存在或无权访问")
    provider = db.get(ServiceProvider, assignment.provider_id)
    _require_provider_operator(db, actor, provider, users=users)
    if assignment.status != "invited" or assignment.round_no != expected_round:
        raise HTTPException(409, "邀请已处理或轮次已变化")
    if accept and (job.status != JobStatus.open or job.confirmed_at is None or assignment.job_version != job.version):
        raise HTTPException(409, "邀请对应的需求版本已失效")
    if not accept and not (reason or "").strip():
        raise HTTPException(422, "拒绝邀请时必须填写原因")
    old = assignment.status
    now = datetime.now()
    assignment.status = "active" if accept else "declined"
    assignment.accepted_by = actor.id if accept else None
    assignment.accepted_at = now if accept else None
    assignment.owner_user_id = actor.id if accept else None
    if not accept:
        assignment.ended_by, assignment.ended_at, assignment.end_reason = actor.id, now, reason.strip()
    add_event(db, assignment=assignment, actor_id=actor.id,
              event_type="accepted" if accept else "declined", old_status=old, reason=reason,
              payload={"round": assignment.round_no, "owner_user_id": assignment.owner_user_id})
    db.commit()
    db.refresh(assignment)
    return _assignment_view(db, actor, assignment)


@mutation
def end_assignment(db: Session, user: User, assignment_id: int, *,
                   expected_round: int, complete: bool, reason: str | None):
    probe = _get_assignment(db, assignment_id)
    actor, job, assignments, users, agencies = lock_context(db, user.id, probe.job_id,
                                                  provider_ids=[probe.provider_id])
    assignment = next((row for row in assignments if row.id == assignment_id), None)
    if assignment is None:
        raise HTTPException(404, "承接记录不存在")
    provider = db.get(ServiceProvider, assignment.provider_id)
    customer = (actor.role == UserRole.recruiter and actor.company_id == job.client_company_id
                and actor.company_role == CompanyRole.manager)
    subject = False
    if provider.kind == "individual":
        subject = provider.user_id == actor.id and actor.role == UserRole.headhunter
    elif provider.agency_id is not None:
        subject = _active_manager(db, actor.id, provider.agency_id, users=users)
    if not customer and not subject:
        raise HTTPException(403, "无权结束该承接")
    if not customer:
        _require_provider_operator(db, actor, provider, users=users)
    if complete and not customer:
        raise HTTPException(403, "仅客户主管可以确认承接完成")
    if assignment.round_no != expected_round:
        raise HTTPException(409, "承接轮次已变化")
    allowed = ("active",) if complete else ("active", "invited")
    if assignment.status not in allowed:
        raise HTTPException(409, "当前承接状态不允许该操作")
    if not (reason or "").strip():
        raise HTTPException(422, "结束承接时必须填写原因")
    old = assignment.status
    assignment.status = "completed" if complete else "cancelled"
    assignment.ended_by, assignment.ended_at, assignment.end_reason = actor.id, datetime.now(), reason.strip()
    add_event(db, assignment=assignment, actor_id=actor.id,
              event_type=assignment.status, old_status=old, reason=reason,
              payload={"round": assignment.round_no})
    db.commit()
    db.refresh(assignment)
    return _assignment_view(db, actor, assignment)


@mutation
def transfer_owner(db: Session, user: User, assignment_id: int, *,
                   expected_round: int, expected_owner_user_id: int | None, owner_user_id: int):
    probe = _get_assignment(db, assignment_id)
    actor, job, assignments, users, agencies = lock_context(
        db, user.id, probe.job_id, provider_ids=[probe.provider_id], user_ids=[owner_user_id],
    )
    assignment = next((row for row in assignments if row.id == assignment_id), None)
    provider = db.get(ServiceProvider, assignment.provider_id) if assignment else None
    if assignment is None or provider.kind != "agency":
        raise HTTPException(409, "仅机构任务支持负责人转派")
    if not _active_manager(db, actor.id, provider.agency_id, users=users):
        raise HTTPException(403, "仅本机构主管可以转派任务")
    if not _provider_active(db, provider, users):
        raise HTTPException(409, "机构已停用")
    if (assignment.status != "active" or assignment.round_no != expected_round or
            assignment.job_version != job.version or job.confirmed_at is None or job.status == JobStatus.closed):
        raise HTTPException(409, "仅有效承接支持转派，或轮次已变化")
    if assignment.owner_user_id != expected_owner_user_id:
        raise HTTPException(409, "负责人已发生变化，请刷新后重试")
    new_owner = users.get(owner_user_id)
    if not new_owner or not new_owner.enabled or new_owner.role != UserRole.headhunter or not _active_member(
        db, owner_user_id, provider.agency_id, users=users
    ):
        raise HTTPException(409, "负责人必须是同机构启用的有效猎头成员")
    old_owner = assignment.owner_user_id
    assignment.owner_user_id = owner_user_id
    add_event(db, assignment=assignment, actor_id=actor.id, event_type="reassigned",
              old_status=assignment.status,
              payload={"round": assignment.round_no, "from_owner_user_id": old_owner,
                       "to_owner_user_id": owner_user_id})
    db.commit()
    db.refresh(assignment)
    return _assignment_view(db, actor, assignment)


def list_assignments(db: Session, user: User):
    query = db.query(JobAssignment).join(Job, Job.id == JobAssignment.job_id).join(
        ServiceProvider, ServiceProvider.id == JobAssignment.provider_id
    )
    query = query.filter(assignment_visibility(user))
    return [_assignment_view(db, user, row) for row in query.order_by(
        JobAssignment.updated_at.desc(), JobAssignment.id.desc()).all()]


def get_assignment(db: Session, user: User, assignment_id: int):
    assignment = _get_assignment(db, assignment_id)
    _require_visible(db, user, assignment)
    return _assignment_view(db, user, assignment)


def list_assignment_events(db: Session, user: User, assignment_id: int):
    assignment = _get_assignment(db, assignment_id)
    _require_visible(db, user, assignment)
    return [AssignmentEventOut.model_validate(row) for row in events_for_assignment(db, assignment.id)]
