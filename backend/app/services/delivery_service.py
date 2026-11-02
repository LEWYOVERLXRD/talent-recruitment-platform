"""猎头私有沟通、一次性推荐交付及客户反馈。"""
from datetime import datetime, timezone
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import and_, exists, or_, select

from app.models import (
    Agency, AgencyMember, Application, ApplicationRecordKind, ApplicationReviewStatus, Candidate, CandidateSource, Communication, Company, Job, JobAssignment,
    JobStatus, Recommendation, RecommendationFeedback, RecommendationStatus,
    Resume, ServiceProvider, User, UserRole,
)
from app.services.agency_service import mutation
from app.services.candidate_ownership import lock_candidate_for_write
from app.services.job_access import task_visibility
from app.services.job_locks import lock_context, lock_match_context
from app.services.resume_files import safe_path


def _candidate_context(db, user, candidate_id, job_id=None):
    context_job_id = job_id or _candidate_job_probe(db, candidate_id)
    actor, job, candidate, assignments, users, members, providers, agencies = lock_match_context(
        db, user.id, context_job_id, candidate_id,
    )
    provider = providers.get(candidate.provider_id)
    if actor.role != UserRole.admin:
        if actor.role != UserRole.headhunter or not _candidate_access(actor, candidate, provider, members, agencies):
            raise HTTPException(403, "当前已无候选人访问权限")
    return actor, job, candidate, assignments, provider, members, agencies


def _candidate_job_probe(db, candidate_id):
    row = db.query(JobAssignment.job_id).join(
        ServiceProvider, ServiceProvider.id == JobAssignment.provider_id
    ).join(Candidate, Candidate.provider_id == ServiceProvider.id).filter(
        Candidate.id == candidate_id, JobAssignment.status == "active"
    ).order_by(JobAssignment.job_id).first()
    if row:
        return row[0]
    raise HTTPException(422, "一般沟通应使用不关联需求的记录入口")


def _candidate_access(user, candidate, provider, members, agencies):
    if not user.enabled or user.role != UserRole.headhunter or provider is None:
        return False
    if provider.kind == "individual":
        return provider.user_id == user.id and candidate.owner_user_id == user.id
    agency = agencies.get(provider.agency_id)
    member = next((m for m in members if m.agency_id == provider.agency_id and m.user_id == user.id), None)
    return bool(agency and agency.status == "active" and member and member.status == "active" and
                (member.role == "manager" or candidate.owner_user_id == user.id))


@mutation
def add_communication(db, user, candidate_id, payload):
    if user.role != UserRole.headhunter:
        raise HTTPException(403, "仅猎头可以记录候选人沟通")
    if payload.job_id is None:
        candidate = lock_candidate_for_write(db, user, candidate_id)
        row = Communication(candidate_id=candidate.id, job_id=None, comm_type=payload.comm_type,
                            content=payload.content.strip(), result=payload.result,
                            communicated_at=payload.communicated_at, follow_up_at=payload.follow_up_at,
                            created_by=user.id)
        db.add(row)
        db.flush()
        return row
    actor, job, candidate, assignments, provider, members, agencies = _candidate_context(
        db, user, candidate_id, payload.job_id,
    )
    assignment = next((a for a in assignments if a.job_id == job.id and a.provider_id == candidate.provider_id), None)
    if (not assignment or assignment.status != "active" or assignment.job_version != job.version
            or job.status == JobStatus.closed or job.confirmed_at is None):
        raise HTTPException(403, "当前无权为该需求记录沟通")
    row = Communication(candidate_id=candidate.id, job_id=job.id, comm_type=payload.comm_type,
                        content=payload.content.strip(), result=payload.result,
                        communicated_at=payload.communicated_at, follow_up_at=payload.follow_up_at,
                        created_by=actor.id)
    db.add(row)
    db.flush()
    return row


def list_communications(db, user, candidate_id, page, size):
    # Current archive permission is checked before returning any private work notes.
    from app.services.candidate_service import get_candidate_detail
    get_candidate_detail(db, current_user=user, candidate_id=candidate_id)
    query = db.query(Communication).filter(Communication.candidate_id == candidate_id)
    total = query.count()
    rows = query.order_by(Communication.communicated_at.desc(), Communication.id.desc()).offset(
        (page - 1) * size).limit(size).all()
    return {"total": total, "items": rows}


def get_communication(db, user, communication_id):
    row = db.get(Communication, communication_id)
    if row is None:
        raise HTTPException(404, "沟通记录不存在或无权访问")
    from app.services.candidate_service import get_candidate_detail
    get_candidate_detail(db, current_user=user, candidate_id=row.candidate_id)
    return row


def _assignment_for_user(db, user, assignment_id, candidate_id=None):
    assignment = db.get(JobAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(404, "需求承接不存在或无权访问")
    job = db.get(Job, assignment.job_id)
    candidate = db.get(Candidate, candidate_id) if candidate_id else None
    provider = db.get(ServiceProvider, assignment.provider_id)
    if candidate is not None and candidate.provider_id != assignment.provider_id:
        raise HTTPException(404, "候选人或需求承接不存在或无权访问")
    if user.role == UserRole.admin:
        allowed = user.enabled
    elif user.role == UserRole.headhunter:
        agency = db.get(Agency, provider.agency_id) if provider.kind == "agency" else None
        member = db.query(AgencyMember).filter_by(
            user_id=user.id, agency_id=provider.agency_id, status="active"
        ).first() if provider.kind == "agency" else None
        current_assignment = bool(user.enabled and (
            (provider.kind == "individual" and provider.user_id == user.id and
             not db.query(AgencyMember.id).filter_by(user_id=user.id, status="active").first()) or
            (provider.kind == "agency" and agency and agency.status == "active" and member and
             (member.role == "manager" or (assignment.owner_user_id == user.id and
              assignment.status == "active" and assignment.job_version == job.version and
              job.confirmed_at is not None and job.status != JobStatus.closed)))
        ))
        allowed = current_assignment or bool(
            user.enabled and provider.kind == "individual" and provider.user_id == user.id and
            not db.query(AgencyMember.id).filter_by(user_id=user.id, status="active").first()
        ) or bool(
            user.enabled and provider.kind == "agency" and agency and agency.status == "active" and member and
            (member.role == "manager" or assignment.owner_user_id == user.id)
        )
    else:
        allowed = False
    if not allowed:
        raise HTTPException(404, "需求承接不存在或无权访问")
    return assignment, job, candidate, provider


def _current_task_ok(user, assignment, job, candidate, provider, db):
    if (not user.enabled or user.role != UserRole.headhunter or assignment.status != "active"
            or assignment.job_version != job.version or job.status != JobStatus.open
            or job.confirmed_at is None):
        return False
    if candidate is not None and candidate.provider_id != provider.id:
        return False
    if provider.kind == "individual":
        return provider.user_id == user.id and (candidate is None or candidate.owner_user_id == user.id)
    member = db.query(AgencyMember).filter_by(
        agency_id=provider.agency_id, user_id=user.id, status="active"
    ).first()
    return bool(member and (member.role == "manager" or assignment.owner_user_id == user.id) and
                (candidate is None or member.role == "manager" or candidate.owner_user_id == user.id))


def _recommendation_view(db, row, user, *, internal=False):
    assignment = db.get(JobAssignment, row.assignment_id) if row.assignment_id else None
    job = db.get(Job, row.job_id)
    candidate = db.get(Candidate, row.candidate_id)
    if assignment is None:
        if user.role != UserRole.admin:
            raise HTTPException(404, "推荐记录不存在或无权访问")
        return {"id": row.id, "status": row.status.value, "historical_pending_verification": True}
    if assignment.job_id != row.job_id or job is None:
        raise HTTPException(404, "推荐记录不存在或无权访问")
    provider = db.get(ServiceProvider, assignment.provider_id)
    delivered = row.delivery_snapshot is not None
    is_customer = user.role == UserRole.recruiter and user.enabled and user.company_id == job.client_company_id
    if user.role == UserRole.admin:
        allowed, current_internal = True, True
    elif is_customer:
        allowed, current_internal = row.delivery_snapshot is not None, False
    elif user.role == UserRole.headhunter:
        current_internal = _current_task_ok(user, assignment, job, candidate, provider, db)
        history_access = delivered and _has_fixed_history_right(db, user, assignment, provider)
        allowed = current_internal or history_access
    else:
        allowed, current_internal = False, False
    if not allowed:
        raise HTTPException(404, "推荐记录不存在或无权访问")
    if delivered and not current_internal and user.role != UserRole.admin:
        return {"id": row.id, "job_id": row.job_id, "job_title": row.delivery_snapshot.get("job", {}).get("title"),
                "application_id": row.application_id,
                "status": row.status.value, "version": row.version, "delivery_snapshot": row.delivery_snapshot,
                "recommended_at": row.recommended_at, "recommended_by": row.recommended_by,
                "can_edit": False, "can_feedback": is_customer}
    result = {"id": row.id, "job_id": row.job_id, "job_title": job.title, "candidate_id": row.candidate_id,
              "assignment_id": row.assignment_id, "assignment_round": row.assignment_round,
              "application_id": row.application_id,
              "job_version": row.job_version, "status": row.status.value, "version": row.version,
              "resume_id": row.resume_id, "recommendation_note": row.recommendation_note,
              "recommended_at": row.recommended_at, "recommended_by": row.recommended_by,
              "can_edit": bool(current_internal and not delivered), "can_feedback": False}
    if current_internal or user.role == UserRole.admin:
        result.update({"preparation_communication_id": row.preparation_communication_id,
                       "share_basis": row.share_basis, "share_confirmed_at": row.share_confirmed_at,
                       "delivery_snapshot": row.delivery_snapshot})
    return result


def _has_fixed_history_right(db, user, assignment, provider):
    if not user.enabled:
        return False
    if provider.kind == "individual":
        return provider.user_id == user.id
    agency = db.get(Agency, provider.agency_id)
    member = db.query(AgencyMember).filter_by(
        agency_id=provider.agency_id, user_id=user.id, status="active"
    ).first()
    return bool(agency and agency.status == "active" and member and
                (member.role == "manager" or assignment.owner_user_id == user.id))


@mutation
def create_recommendation(db, user, assignment_id, candidate_id, application_id=None):
    application = None
    selected_resume_id = None
    if application_id is not None:
        application = db.query(Application).filter(Application.id == application_id).populate_existing().with_for_update().first()
        if application is not None and application.record_kind == ApplicationRecordKind.duplicate:
            raise HTTPException(409, "该人选已入库，重复投递不能进入推荐流程")
        if (application is None or application.publisher_user_id != user.id or
                application.review_status in (ApplicationReviewStatus.recommendation_draft,
                                              ApplicationReviewStatus.recommended,
                                              ApplicationReviewStatus.legacy_unrouted)):
            raise HTTPException(404, "投递记录不存在或已进入推荐流程")
        source_candidate_id = application.candidate_id
        if source_candidate_id != candidate_id:
            raise HTTPException(409, "投递与候选人不匹配")
        assignment_probe = db.get(JobAssignment, assignment_id)
        source_candidate = db.query(Candidate).filter(Candidate.id == source_candidate_id).populate_existing().with_for_update().first()
        source_resume = db.get(Resume, application.resume_id)
        if (assignment_probe is None or source_candidate is None or source_resume is None or
                source_resume.candidate_id != source_candidate.id or assignment_probe.job_id != application.job_id or
                application.assignment_id != assignment_id or application.working_candidate_id is None or
                application.working_resume_id is None):
            raise HTTPException(409, "投递与需求承接不匹配")
        if source_candidate.provider_id is not None or source_candidate.candidate_user_id != application.applicant_user_id:
            raise HTTPException(409, "自助候选人归属已变化")
        # 投递时已经建立猎头侧工作档案；推荐阶段复用它，避免重复克隆或改变归属。
        candidate_probe = db.get(Candidate, application.working_candidate_id)
        working_resume = db.get(Resume, application.working_resume_id)
        if (candidate_probe is None or working_resume is None or
                candidate_probe.provider_id != assignment_probe.provider_id or
                candidate_probe.owner_user_id != user.id or working_resume.candidate_id != candidate_probe.id):
            raise HTTPException(409, "投递的猎头工作档案已变化")
        candidate_id = candidate_probe.id
        selected_resume_id = working_resume.id
    probe, job_probe, candidate_probe, provider_probe = _assignment_for_user(db, user, assignment_id, candidate_id)
    actor, job, candidate, assignments, users, members, providers, agencies = lock_match_context(
        db, user.id, job_probe.id, candidate_id,
    )
    assignment = next((a for a in assignments if a.id == probe.id), None)
    provider = providers.get(assignment.provider_id) if assignment else None
    if assignment is None or assignment.job_id != job.id or candidate.provider_id != provider.id:
        raise HTTPException(409, "候选人或承接主体已变化")
    if not _current_task_ok(user, assignment, job, candidate, provider, db):
        raise HTTPException(403, "当前无权为该承接准备推荐")
    existing = db.query(Recommendation).filter_by(assignment_id=assignment.id,
                                                   candidate_id=candidate.id).first()
    if existing:
        raise HTTPException(409, "该承接下此候选人已有推荐生命周期")
    row = Recommendation(job_id=job.id, candidate_id=candidate.id, assignment_id=assignment.id,
                         assignment_round=assignment.round_no, created_by=user.id,
                         application_id=application_id, resume_id=selected_resume_id,
                         job_version=job.version, status=RecommendationStatus.pending_contact,
                         version=1)
    db.add(row)
    if application is not None:
        application.review_status = ApplicationReviewStatus.recommendation_draft
        application.reviewed_by = user.id
        application.reviewed_at = datetime.now()
    db.flush()
    return _recommendation_view(db, row, user, internal=True)


@mutation
def update_recommendation(db, user, recommendation_id, payload):
    probe = db.get(Recommendation, recommendation_id)
    if probe is None or probe.assignment_id is None:
        raise HTTPException(404, "推荐草稿不存在或无权访问")
    _, job_probe, _, _ = _assignment_for_user(db, user, probe.assignment_id, probe.candidate_id)
    actor, job, candidate, assignments, users, members, providers, agencies = lock_match_context(
        db, user.id, job_probe.id, probe.candidate_id,
    )
    row = db.query(Recommendation).filter_by(id=recommendation_id).populate_existing().with_for_update().first()
    assignment = next((a for a in assignments if a.id == row.assignment_id), None)
    provider = providers.get(assignment.provider_id) if assignment else None
    if assignment is None or assignment.job_id != job.id or candidate.provider_id != provider.id:
        raise HTTPException(409, "候选人或承接主体已变化")
    if not _current_task_ok(user, assignment, job, candidate, provider, db):
        raise HTTPException(403, "当前无权修改推荐草稿")
    if row.delivery_snapshot is not None or row.version != payload.expected_version:
        raise HTTPException(409, "推荐已交付或版本已变化")
    values = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)
    communication_id = values.pop("communication_id", None)
    if "communication_id" in payload.model_fields_set:
        if communication_id is None:
            row.preparation_communication_id = None
        else:
            comm = db.get(Communication, communication_id)
            if not comm or comm.candidate_id != row.candidate_id or comm.job_id not in (None, job.id):
                raise HTTPException(422, "沟通依据必须属于该候选人且未关联其他需求")
            row.preparation_communication_id = communication_id
    if "resume_id" in values and values["resume_id"] is not None:
        resume = db.get(Resume, values["resume_id"])
        if not resume or resume.candidate_id != row.candidate_id:
            raise HTTPException(422, "简历版本必须属于该候选人")
    for key, value in values.items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    row.version += 1
    db.flush()
    return _recommendation_view(db, row, user, internal=True)


@mutation
def stage_recommendation(db, user, recommendation_id, payload):
    probe = db.get(Recommendation, recommendation_id)
    if probe is None or probe.assignment_id is None:
        raise HTTPException(404, "推荐草稿不存在")
    _, job_probe, _, _ = _assignment_for_user(db, user, probe.assignment_id, probe.candidate_id)
    actor, job, candidate, assignments, users, members, providers, agencies = lock_match_context(
        db, user.id, job_probe.id, probe.candidate_id,
    )
    row = db.query(Recommendation).filter_by(id=recommendation_id).populate_existing().with_for_update().first()
    assignment = next((a for a in assignments if a.id == row.assignment_id), None)
    provider = providers.get(assignment.provider_id) if assignment else None
    if assignment is None or assignment.job_id != job.id or candidate.provider_id != provider.id:
        raise HTTPException(409, "候选人或承接主体已变化")
    if not _current_task_ok(user, assignment, job, candidate, provider, db):
        raise HTTPException(403, "当前任务已失效")
    if row.version != payload.expected_version or row.delivery_snapshot is not None:
        raise HTTPException(409, "推荐版本已变化或已交付")
    comm = db.get(Communication, payload.communication_id)
    if not comm or comm.candidate_id != row.candidate_id or comm.job_id not in (None, job.id):
        raise HTTPException(422, "请选择该候选人针对当前需求或一般跟进的真实沟通记录")
    if comm.result == "not_interested":
        raise HTTPException(422, "候选人暂无意向，不能进入待推荐")
    if payload.status == "contacted" and row.status != RecommendationStatus.pending_contact:
        raise HTTPException(409, "当前阶段不能标记为已沟通")
    if payload.status == "pending_recommend" and row.status not in (
        RecommendationStatus.pending_contact, RecommendationStatus.contacted
    ):
        raise HTTPException(409, "当前阶段不能进入待推荐")
    row.preparation_communication_id = comm.id
    row.status = RecommendationStatus(payload.status)
    row.version += 1
    db.flush()
    return _recommendation_view(db, row, user, internal=True)


@mutation
def refresh_recommendation_context(db, user, recommendation_id, payload):
    probe = db.get(Recommendation, recommendation_id)
    if probe is None or probe.assignment_id is None:
        raise HTTPException(404, "推荐草稿不存在")
    _, job_probe, _, _ = _assignment_for_user(db, user, probe.assignment_id, probe.candidate_id)
    actor, job, candidate, assignments, users, members, providers, agencies = lock_match_context(
        db, user.id, job_probe.id, probe.candidate_id,
    )
    row = db.query(Recommendation).filter_by(id=recommendation_id).populate_existing().with_for_update().first()
    assignment = next((a for a in assignments if a.id == row.assignment_id), None)
    provider = providers.get(assignment.provider_id) if assignment else None
    if assignment is None or assignment.job_id != job.id or candidate.provider_id != provider.id:
        raise HTTPException(409, "候选人或承接主体已变化")
    if row.delivery_snapshot is not None or row.version != payload.expected_version:
        raise HTTPException(409, "推荐已交付或版本已变化")
    if not _current_task_ok(user, assignment, job, candidate, provider, db):
        raise HTTPException(403, "当前任务已失效")
    if job.version == row.job_version and assignment.round_no == row.assignment_round:
        raise HTTPException(409, "需求版本和承接轮次均未变化")
    if (payload.job_version, payload.assignment_round) != (job.version, assignment.round_no):
        raise HTTPException(409, "提交的需求版本或承接轮次已过期")
    row.job_version, row.assignment_round = job.version, assignment.round_no
    row.status = RecommendationStatus.pending_contact
    row.resume_id = row.preparation_communication_id = None
    row.recommendation_note = row.share_basis = None
    row.share_confirmed_at = None
    row.share_recorded_by = None
    row.version += 1
    db.flush()
    return _recommendation_view(db, row, user, internal=True)


def _provider_name(db, provider):
    if provider.kind == "agency":
        agency = db.get(Agency, provider.agency_id)
        return agency.name if agency else None
    hunter = db.get(User, provider.user_id)
    return (hunter.real_name or hunter.username) if hunter else None


@mutation
def submit_recommendation(db, user, recommendation_id, payload):
    probe = db.get(Recommendation, recommendation_id)
    if probe is None or probe.assignment_id is None:
        raise HTTPException(404, "推荐草稿不存在")
    _, job_probe, _, _ = _assignment_for_user(db, user, probe.assignment_id, probe.candidate_id)
    actor, job, candidate, assignments, users, members, providers, agencies = lock_match_context(
        db, user.id, job_probe.id, probe.candidate_id,
    )
    assignment = next((a for a in assignments if a.id == probe.assignment_id), None)
    if assignment is not None and probe.resume_id is not None:
        db.query(Resume).filter_by(id=probe.resume_id, candidate_id=probe.candidate_id).populate_existing().with_for_update().first()
    row = db.query(Recommendation).filter_by(id=recommendation_id).populate_existing().with_for_update().first()
    provider = providers.get(assignment.provider_id) if assignment else None
    if assignment is None or candidate.provider_id != provider.id:
        raise HTTPException(409, "候选人或承接主体已变化")
    if not _current_task_ok(user, assignment, job, candidate, provider, db):
        raise HTTPException(403, "当前任务已失效，不能交付")
    if row.version != payload.expected_version or row.delivery_snapshot is not None:
        raise HTTPException(409, "推荐已变化或已交付")
    if (row.status != RecommendationStatus.pending_recommend or row.job_version != job.version
            or row.assignment_round != assignment.round_no):
        raise HTTPException(409, "推荐阶段、需求版本或承接轮次不匹配")
    comm = db.get(Communication, row.preparation_communication_id) if row.preparation_communication_id else None
    resume = db.get(Resume, row.resume_id) if row.resume_id else None
    if not comm or comm.candidate_id != candidate.id or comm.job_id not in (None, job.id) or comm.result == "not_interested":
        raise HTTPException(422, "提交前需要有效沟通依据")
    if (not resume or resume.candidate_id != candidate.id or resume.parse_status != "success"
            or not (resume.parsed_text or "").strip() or not resume.file_sha256):
        raise HTTPException(422, "提交前需要已成功解析且可核验的简历版本")
    if not (row.recommendation_note or "").strip():
        raise HTTPException(422, "请填写推荐说明")
    basis = payload.share_basis.strip()
    now = datetime.now(timezone.utc)
    confirmed_at = payload.share_confirmed_at
    if confirmed_at.tzinfo is None:
        confirmed_at = confirmed_at.replace(tzinfo=timezone.utc)
    if not basis or confirmed_at > now:
        raise HTTPException(422, "请记录真实的材料共享依据和确认时间")
    try:
        path = safe_path(resume.file_path)
        digest = sha256(path.read_bytes()).hexdigest()
    except (HTTPException, OSError):
        raise HTTPException(409, "交付附件不可用，请重新核验简历文件") from None
    if digest != resume.file_sha256:
        raise HTTPException(409, "交付附件摘要不匹配，请重新核验文件")
    company = db.get(Company, job.client_company_id)
    snapshot = {
        "schema_version": 1,
        "job": {"id": job.id, "version": job.version, "title": job.title, "department": job.department,
                "description": job.description, "requirements": job.requirements, "salary_min": job.salary_min,
                "salary_max": job.salary_max, "location": job.location, "company_id": company.id,
                "company_name": company.name},
        "provider": {"id": provider.id, "kind": provider.kind, "name": _provider_name(db, provider)},
        "assignment": {"id": assignment.id, "round": assignment.round_no},
        "recommendation": {"note": row.recommendation_note.strip(), "submitted_at": now.isoformat()},
        "candidate": {"id": candidate.id, "name": candidate.name, "phone": candidate.phone,
                      "email": candidate.email, "current_company": candidate.current_company,
                      "current_position": candidate.current_position,
                      "years_of_experience": candidate.years_of_experience,
                      "education": candidate.education, "expected_salary": candidate.expected_salary,
                      "expected_location": candidate.expected_location},
        "resume": {"id": resume.id, "version": resume.version, "file_name": resume.original_name,
                   "file_type": resume.file_type, "file_size": resume.file_size,
                   "sha256": resume.file_sha256, "parsed_text": resume.parsed_text},
        "sharing_basis_recorded": True,
    }
    row.share_basis, row.share_confirmed_at, row.share_recorded_by = basis, confirmed_at.replace(tzinfo=None), user.id
    row.delivery_snapshot = snapshot
    row.status = RecommendationStatus.recommended
    row.recommended_by, row.recommended_at = user.id, now
    if row.application_id:
        application = db.get(Application, row.application_id)
        if application is not None:
            application.review_status = ApplicationReviewStatus.recommended
            application.reviewed_by = user.id
            application.reviewed_at = now.replace(tzinfo=None)
    row.version += 1
    db.flush()
    return _recommendation_view(db, row, user, internal=True)


def _can_feedback(user, job):
    return bool(user.enabled and user.role == UserRole.recruiter and user.company_id == job.client_company_id)


def _feedback_transition(row, conclusion, feedback_type):
    current = row.status
    if conclusion == "note":
        if current not in (RecommendationStatus.recommended, RecommendationStatus.accepted,
                           RecommendationStatus.interviewing, RecommendationStatus.passed,
                           RecommendationStatus.rejected):
            raise HTTPException(409, "仅已交付推荐可以追加备注")
        return current
    if current == RecommendationStatus.recommended and feedback_type == "recommendation":
        if conclusion in ("accepted", "rejected"):
            return RecommendationStatus(conclusion)
    if current == RecommendationStatus.accepted:
        if conclusion == "interviewing" and feedback_type == "interview":
            return RecommendationStatus.interviewing
        if conclusion == "rejected" and feedback_type == "recommendation":
            return RecommendationStatus.rejected
    if current == RecommendationStatus.interviewing and feedback_type == "interview":
        if conclusion in ("passed", "rejected"):
            return RecommendationStatus(conclusion)
    raise HTTPException(409, "当前推荐状态不允许该反馈")


@mutation
def add_feedback(db, user, recommendation_id, payload):
    probe = db.get(Recommendation, recommendation_id)
    if probe is None or probe.delivery_snapshot is None or probe.assignment_id is None:
        raise HTTPException(404, "已交付推荐不存在或无权访问")
    actor, job, assignments, users, agencies = lock_context(db, user.id, probe.job_id)
    row = db.query(Recommendation).filter_by(id=recommendation_id).populate_existing().with_for_update().first()
    assignment = next((a for a in assignments if a.id == row.assignment_id), None)
    if (row.delivery_snapshot is None or row.assignment_id is None or assignment is None
            or assignment.job_id != row.job_id):
        raise HTTPException(404, "已交付推荐不存在或无权访问")
    if not _can_feedback(actor, job):
        raise HTTPException(404, "已交付推荐不存在或无权访问")
    if row.version != payload.expected_version:
        raise HTTPException(409, "推荐状态已变化，请刷新后重试")
    content = payload.content.strip()
    target = _feedback_transition(row, payload.conclusion, payload.feedback_type)
    if payload.conclusion == "rejected" and len(content) < 20:
        raise HTTPException(422, "拒收或未通过原因至少 20 个字符")
    previous = row.status.value
    row.status = target
    row.version += 1
    row.client_feedback = content
    if payload.conclusion == "rejected":
        row.reject_reason = content
    if payload.feedback_type == "interview":
        row.interview_feedback = content
    event = RecommendationFeedback(recommendation_id=row.id, actor_id=actor.id,
                                   feedback_type=payload.feedback_type, conclusion=payload.conclusion,
                                   content=content, from_status=previous, to_status=target.value,
                                   recommendation_version=row.version)
    db.add(event)
    db.flush()
    return event


def list_feedbacks(db, user, recommendation_id, page, size):
    row = db.get(Recommendation, recommendation_id)
    if row is None or row.delivery_snapshot is None:
        raise HTTPException(404, "已交付推荐不存在或无权访问")
    view = _recommendation_view(db, row, user)
    del view
    query = db.query(RecommendationFeedback).filter(RecommendationFeedback.recommendation_id == row.id)
    total = query.count()
    items = query.order_by(RecommendationFeedback.created_at, RecommendationFeedback.id).offset(
        (page - 1) * size).limit(size).all()
    return {"total": total, "items": items}


def get_recommendation(db, user, recommendation_id):
    row = db.get(Recommendation, recommendation_id)
    if row is None:
        raise HTTPException(404, "推荐记录不存在或无权访问")
    return _recommendation_view(db, row, user)


def list_recommendations(db, user, page, size):
    query = db.query(Recommendation)
    if user.role == UserRole.recruiter and user.enabled and user.company_id:
        query = query.join(Job, Job.id == Recommendation.job_id).filter(
            Job.client_company_id == user.company_id, Recommendation.delivery_snapshot.is_not(None))
    elif user.role == UserRole.headhunter and user.enabled:
        individual = and_(ServiceProvider.kind == "individual", ServiceProvider.user_id == user.id)
        agency_history = exists(select(AgencyMember.id).select_from(AgencyMember).join(
            Agency, Agency.id == AgencyMember.agency_id).where(
                AgencyMember.agency_id == ServiceProvider.agency_id,
                AgencyMember.user_id == user.id, AgencyMember.status == "active",
                Agency.status == "active",
                or_(AgencyMember.role == "manager", JobAssignment.owner_user_id == user.id),
            ).correlate(ServiceProvider, JobAssignment))
        historical_access = or_(individual, and_(ServiceProvider.kind == "agency", agency_history))
        active_draft = and_(Recommendation.delivery_snapshot.is_(None),
                            task_visibility(user, same_candidate=True))
        query = query.join(JobAssignment, JobAssignment.id == Recommendation.assignment_id).join(
            ServiceProvider, ServiceProvider.id == JobAssignment.provider_id).join(
            Job, Job.id == Recommendation.job_id).join(Candidate, Candidate.id == Recommendation.candidate_id).filter(
                JobAssignment.job_id == Recommendation.job_id,
                historical_access,
                or_(Recommendation.delivery_snapshot.is_not(None), active_draft))
    elif user.role != UserRole.admin or not user.enabled:
        raise HTTPException(403, "当前角色无权查看推荐记录")
    total = query.count()
    rows = query.order_by(Recommendation.updated_at.desc(), Recommendation.id.desc()).offset(
        (page - 1) * size).limit(size).all()
    items = [_recommendation_view(db, row, user) for row in rows]
    return {"total": total, "items": items}


def download_recommendation_resume(db, user, recommendation_id):
    row = db.get(Recommendation, recommendation_id)
    if row is None or row.delivery_snapshot is None:
        raise HTTPException(404, "已交付附件不存在或无权访问")
    view = _recommendation_view(db, row, user)
    del view
    resume_data = row.delivery_snapshot.get("resume", {})
    resume = db.get(Resume, resume_data.get("id"))
    if not resume or resume.file_sha256 != resume_data.get("sha256"):
        raise HTTPException(409, "交付附件不可用")
    try:
        path = safe_path(resume.file_path)
        digest = sha256(path.read_bytes()).hexdigest()
    except (HTTPException, OSError):
        raise HTTPException(409, "交付附件不可用") from None
    if digest != resume_data.get("sha256"):
        raise HTTPException(409, "交付附件摘要不匹配")
    return resume, path
