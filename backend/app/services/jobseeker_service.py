"""求职者自助档案、简历和投递业务。"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import Application, ApplicationRecordKind, ApplicationReviewStatus, ApplicationSource, ApplicationStatus, Candidate, CandidateSource, Job, Resume, User, UserRole, JobAssignment
from app.services.public_jobs import receiving_assignments
from app.services.agency_service import mutation
from app.services.job_locks import lock_context
from app.services.candidate_service import get_candidate_detail


def require_jobseeker(user: User) -> None:
    if not user.enabled or user.role != UserRole.jobseeker:
        raise HTTPException(403, "仅求职者可以使用自助求职功能")


def get_or_create_profile(db, user: User) -> Candidate:
    require_jobseeker(user)
    row = db.query(Candidate).filter(Candidate.candidate_user_id == user.id).first()
    if row is not None:
        return row
    row = Candidate(
        name=(user.real_name or user.username).strip(),
        email=user.email,
        phone=user.phone,
        source=CandidateSource.self_apply,
        candidate_user_id=user.id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.query(Candidate).filter(Candidate.candidate_user_id == user.id).first()
        if row is None:
            raise HTTPException(409, "求职者档案创建冲突，请重试") from None
    else:
        db.refresh(row)
    return row


def update_profile(db, user: User, payload) -> Candidate:
    row = get_or_create_profile(db, user)
    data = payload.model_dump(exclude_unset=True)
    data.pop("source", None)
    data.pop("ownership", None)
    data.pop("owner_user_id", None)
    if "name" in data and not (data["name"] or "").strip():
        raise HTTPException(422, "姓名不能为空")
    for key, value in data.items():
        setattr(row, key, value)
    row.source = CandidateSource.self_apply
    db.commit()
    db.refresh(row)
    return row


@mutation
def create_application(db, user: User, *, job_id: int, resume_id: int, assignment_id: int) -> Application:
    profile = get_or_create_profile(db, user)
    job = db.get(Job, job_id)
    assignment = next((a for a in receiving_assignments(db, job_id) if a.id == assignment_id), None) if job else None
    publisher = db.get(User, assignment.owner_user_id) if assignment and assignment.owner_user_id else None
    if job is None or assignment is None or assignment.job_id != job.id or publisher is None:
        raise HTTPException(404, "岗位不存在或当前不接受投递")
    lock_context(db, user.id, job_id, user_ids=(publisher.id,))
    assignment = next((a for a in receiving_assignments(db, job_id) if a.id == assignment_id), None)
    if assignment is None or assignment.owner_user_id != publisher.id:
        raise HTTPException(409, "接收投递的猎头已变化，请刷新岗位后重试")
    profile = db.query(Candidate).filter_by(id=profile.id).populate_existing().with_for_update().one()
    resume = db.query(Resume).filter_by(id=resume_id).populate_existing().with_for_update().first()
    if resume is None or resume.candidate_id != profile.id:
        raise HTTPException(404, "简历不存在或不属于当前求职者")
    existing = (db.query(Application).filter(
        Application.job_id == job.id, Application.candidate_id == profile.id,
    ).order_by(Application.id.asc()).all())
    if any(row.publisher_user_id == publisher.id for row in existing):
        raise HTTPException(409, "你已提交过该猎头的岗位投递")
    primary = next((row for row in existing if row.record_kind == ApplicationRecordKind.primary), None)
    now = datetime.now()
    if primary is not None:
        row = Application(
            job_id=job.id, candidate_id=profile.id, resume_id=resume.id,
            applicant_user_id=user.id, publisher_user_id=publisher.id,
            assignment_id=assignment.id, source=ApplicationSource.self_apply,
            status=ApplicationStatus.submitted, record_kind=ApplicationRecordKind.duplicate,
            canonical_application_id=primary.id, submitted_at=now, status_updated_at=now,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "投递记录已存在，请刷新后查看") from None
        db.refresh(row)
        return row
    working_candidate = Candidate(
        name=profile.name, gender=profile.gender, phone=profile.phone, email=profile.email,
        current_company=profile.current_company, current_position=profile.current_position,
        years_of_experience=profile.years_of_experience, education=profile.education,
        expected_salary=profile.expected_salary, expected_location=profile.expected_location,
        source=CandidateSource.self_apply, created_by=publisher.id,
        provider_id=assignment.provider_id, owner_user_id=publisher.id,
    )
    db.add(working_candidate)
    db.flush()
    working_resume = Resume(
        candidate_id=working_candidate.id, file_path=resume.file_path, original_name=resume.original_name,
        file_type=resume.file_type, parsed_text=resume.parsed_text, parse_status=resume.parse_status,
        is_primary=True, version=1, uploaded_by=publisher.id, file_size=resume.file_size,
        file_sha256=resume.file_sha256, parse_error=resume.parse_error, parsed_at=resume.parsed_at,
        extraction_status="pending", skill_revision=0,
    )
    db.add(working_resume)
    db.flush()
    row = Application(
        job_id=job.id,
        candidate_id=profile.id,
        resume_id=resume.id,
        applicant_user_id=user.id,
        publisher_user_id=publisher.id,
        assignment_id=assignment.id,
        working_candidate_id=working_candidate.id,
        working_resume_id=working_resume.id,
        source=ApplicationSource.self_apply,
        status=ApplicationStatus.submitted,
        record_kind=ApplicationRecordKind.primary,
        submitted_at=now,
        status_updated_at=now,
    )
    db.add(row)
    db.flush()
    row.canonical_application_id = row.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "投递记录已存在，请刷新后查看") from None
    db.refresh(row)
    return row


def list_my_applications(db, user: User):
    profile = get_or_create_profile(db, user)
    return (
        db.query(Application)
        .filter(Application.candidate_id == profile.id, Application.applicant_user_id == user.id)
        .order_by(Application.created_at.desc(), Application.id.desc())
        .all()
    )


def get_my_application(db, user: User, application_id: int) -> Application:
    profile = get_or_create_profile(db, user)
    row = db.query(Application).filter(
        Application.id == application_id,
        Application.candidate_id == profile.id,
        Application.applicant_user_id == user.id,
    ).first()
    if row is None:
        raise HTTPException(404, "投递记录不存在")
    return row


def _require_internal(user: User) -> None:
    if not user.enabled or user.role not in (UserRole.admin, UserRole.headhunter):
        raise HTTPException(403, "当前角色无权处理求职投递")


def _application_for_operator(db, user: User, application_id: int) -> Application:
    _require_internal(user)
    row = db.get(Application, application_id)
    if row is None:
        raise HTTPException(404, "投递记录不存在")
    if user.role == UserRole.headhunter and row.publisher_user_id != user.id:
        raise HTTPException(404, "投递记录不存在")
    if row.record_kind == ApplicationRecordKind.duplicate:
        raise HTTPException(409, "该人选已入库，重复投递不能进入筛选或推荐流程")
    return row


def list_internal_applications(db, user: User):
    _require_internal(user)
    query = db.query(Application)
    if user.role == UserRole.headhunter:
        query = query.filter(Application.publisher_user_id == user.id)
    return query.order_by(Application.created_at.desc(), Application.id.desc()).all()


def get_application_resume(db, user: User, application_id: int) -> Resume:
    row = _application_for_operator(db, user, application_id)
    resume = db.get(Resume, row.resume_id)
    candidate = db.get(Candidate, row.candidate_id)
    if (resume is None or candidate is None or resume.candidate_id != row.candidate_id or
            candidate.candidate_user_id != row.applicant_user_id):
        raise HTTPException(404, "投递简历不存在")
    return resume


def update_application_status(db, user: User, application_id: int, payload) -> Application:
    row = _application_for_operator(db, user, application_id)
    job = db.get(Job, row.job_id)
    if job is None:
        raise HTTPException(404, "投递记录不存在")
    target = ApplicationStatus(payload.status)
    transitions = {
        ApplicationStatus.submitted: {ApplicationStatus.screening, ApplicationStatus.rejected},
        ApplicationStatus.screening: {ApplicationStatus.interview, ApplicationStatus.rejected},
        ApplicationStatus.interview: {ApplicationStatus.offer, ApplicationStatus.rejected},
    }
    if target not in transitions.get(row.status, set()):
        raise HTTPException(409, "当前投递状态不能推进到目标状态")
    if target == ApplicationStatus.rejected and not (payload.rejection_reason_note or "").strip():
        raise HTTPException(422, "拒收时必须填写原因")
    row.status = target
    row.rejection_reason_category = (payload.rejection_reason_category or "").strip() or None
    row.rejection_reason_note = (payload.rejection_reason_note or "").strip() or None
    row.status_updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row


def review_application(db, user: User, application_id: int, payload) -> Application:
    row = _application_for_operator(db, user, application_id)
    if payload.decision == "not_recommended" and not (payload.review_note or "").strip():
        raise HTTPException(422, "暂不推荐时必须填写内部原因")
    if row.review_status in (ApplicationReviewStatus.recommendation_draft, ApplicationReviewStatus.recommended):
        raise HTTPException(409, "该投递已进入推荐流程，不能覆盖审核结果")
    row.review_status = ApplicationReviewStatus(payload.decision)
    row.review_note = (payload.review_note or "").strip() or None
    row.reviewed_by = user.id
    row.reviewed_at = datetime.now()
    db.commit()
    db.refresh(row)
    return row
