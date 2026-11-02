"""招聘需求草稿、客户确认及按主体隔离的访问。"""
from datetime import datetime
from functools import wraps

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.crud.job import create_job as crud_create_job
from app.crud.job import get_job_by_id, list_jobs
from app.models.job import Job, JobSource, JobStatus
from app.models.job_assignment import JobAssignment
from app.models.user import CompanyRole, User, UserRole
from app.schemas.job import JobCreate, JobUpdate
from app.services.job_access import job_visibility, task_visibility
from app.services.public_jobs import public_job_scope
from app.services.job_locks import lock_context


def _http(code: int, detail: str):
    raise HTTPException(status_code=code, detail=detail)


def mutation(function):
    @wraps(function)
    def wrapped(db, *args, **kwargs):
        try:
            return function(db, *args, **kwargs)
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "招聘需求已发生变化，请刷新后重试") from None
        except Exception:
            db.rollback()
            raise
    return wrapped


def can_access_job(user: User, job: Job, db: Session | None = None) -> bool:
    if not user.enabled:
        return False
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.recruiter:
        return user.company_id is not None and job.client_company_id == user.company_id
    if user.role == UserRole.jobseeker:
        return db is not None and db.query(Job.id).filter(Job.id == job.id, public_job_scope()).first() is not None
    if user.role != UserRole.headhunter or db is None:
        return False
    return db.query(Job.id).filter(Job.id == job.id, job_visibility(user)).first() is not None


def can_access_active_job(user: User, job: Job, db: Session) -> bool:
    if not user.enabled:
        return False
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.recruiter:
        return user.company_id is not None and job.client_company_id == user.company_id
    if user.role != UserRole.headhunter:
        return False
    return db.query(Job.id).filter(Job.id == job.id, task_visibility(user)).first() is not None


def can_view_job_contact(user: User, job: Job, db: Session) -> bool:
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.recruiter:
        return user.company_id is not None and job.client_company_id == user.company_id
    return can_access_active_job(user, job, db) and job.status != JobStatus.closed


def can_update_job(user: User, job: Job, db: Session | None = None) -> bool:
    if not user.enabled:
        return False
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.recruiter:
        return (user.company_id == job.client_company_id and
                user.company_role in (CompanyRole.manager, CompanyRole.staff) and
                (job.ever_confirmed_at is None or user.company_role == CompanyRole.manager))
    return (user.role == UserRole.headhunter and job.ever_confirmed_at is None and
            job.created_by == user.id)


def _job_data(payload: JobCreate | JobUpdate) -> dict:
    allowed = {
        "title", "department", "description", "requirements", "salary_min", "salary_max",
        "location", "contact_person", "contact_info", "hiring_count", "priority",
    }
    return {key: value for key, value in payload.model_dump(exclude_unset=True).items() if key in allowed}


def _has_valid_terms(job: Job) -> bool:
    return bool((job.title or "").strip() and
                (job.description or "").strip() and
                (job.requirements or "").strip())


@mutation
def new_job(db: Session, *, current_user: User, payload: JobCreate) -> Job:
    if not current_user.enabled or current_user.role not in (UserRole.recruiter, UserRole.headhunter, UserRole.admin):
        _http(403, "当前角色无权创建招聘需求")
    if current_user.role == UserRole.recruiter:
        if current_user.company_id is None:
            _http(403, "当前招聘方账号未归属企业")
        company_id, source = current_user.company_id, JobSource.client_published
        profile_source = "client_provided"
        if payload.client_company_id is not None:
            _http(422, "企业招聘方不能指定其他客户企业")
    else:
        if payload.client_company_id is None:
            _http(422, "请选择已核验的客户企业")
        from app.models.company import Company
        company = db.get(Company, payload.client_company_id)
        if company is None:
            _http(404, "客户企业不存在")
        company_id, source = company.id, JobSource.headhunter_created
        profile_source = "manual" if current_user.role == UserRole.admin else "headhunter_collected"
    profile_content = payload.job_profile_content
    if profile_content is None:
        profile_content = "\n".join(filter(None, [payload.title, payload.department,
                                                        payload.description, payload.requirements]))
    if not profile_content.strip():
        _http(422, "岗位资料不能为空")
    try:
        job_data = _job_data(payload)
        job_data.pop("title", None)
        job_data.pop("job_profile_content", None)
        job = crud_create_job(
            db, title=payload.title.strip(), client_company_id=company_id,
            created_by=current_user.id, source=source, profile_content=profile_content,
            profile_source=profile_source, **job_data,
        )
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise


def list_job_page(db: Session, *, current_user: User, status_filter=None,
                  keyword=None, page=1, size=20):
    if not current_user.enabled:
        _http(403, "账号已停用")
    if current_user.role == UserRole.recruiter:
        if current_user.company_id is None:
            _http(403, "当前账号未归属任何企业")
        company_id, creator_id = current_user.company_id, None
    elif current_user.role == UserRole.admin:
        company_id, creator_id = None, None
    elif current_user.role == UserRole.headhunter:
        company_id, creator_id = None, None
    elif current_user.role == UserRole.jobseeker:
        company_id, creator_id = None, None
    else:
        _http(403, "当前角色无权查看招聘需求")

    status_obj = None
    if status_filter:
        try:
            status_obj = JobStatus(status_filter)
        except ValueError:
            _http(400, "无效的需求状态")
    page, size = max(1, page), max(1, min(100, size))
    if current_user.role == UserRole.jobseeker:
        query = db.query(Job).filter(
            public_job_scope(),
        )
        if keyword:
            query = query.filter(Job.title.like(f"%{keyword}%"))
        total = query.count()
        items = query.order_by(Job.created_at.desc(), Job.id.desc()).offset((page - 1) * size).limit(size).all()
        return total, items
    if current_user.role != UserRole.headhunter:
        return list_jobs(db, company_id=company_id, status=status_obj,
                         keyword=keyword, offset=(page - 1) * size, limit=size)

    query = db.query(Job).filter(job_visibility(current_user))
    if status_obj is not None:
        query = query.filter(Job.status == status_obj)
    if keyword:
        query = query.filter(Job.title.like(f"%{keyword}%"))
    total = query.count()
    items = query.order_by(Job.created_at.desc(), Job.id.desc()).offset((page - 1) * size).limit(size).all()
    return total, items


def get_job_detail(db: Session, *, current_user: User, job_id: int) -> Job:
    job = get_job_by_id(db, job_id)
    if job is None or not can_access_job(current_user, job, db):
        _http(404, "招聘需求不存在或无权访问")
    return job


def get_job_profile(db: Session, *, current_user: User, job_id: int):
    from app.models.job_profile import JobProfile
    job = get_job_detail(db, current_user=current_user, job_id=job_id)
    draft_owner = job.ever_confirmed_at is None and job.created_by == current_user.id
    if not draft_owner and not can_access_active_job(current_user, job, db):
        _http(404, "岗位资料不存在或无权访问")
    profile = db.get(JobProfile, job.job_profile_id) if job.job_profile_id else None
    if profile is None:
        _http(404, "岗位资料不存在")
    return profile


@mutation
def patch_job(db: Session, *, current_user: User, job_id: int, payload: JobUpdate) -> Job:
    current_user, job, _, _, _ = lock_context(db, current_user.id, job_id)
    if job is None or not current_user.enabled:
        _http(404, "招聘需求不存在或无权访问")
    if current_user.role == UserRole.recruiter:
        if current_user.company_id != job.client_company_id:
            _http(404, "招聘需求不存在或无权访问")
    elif current_user.role == UserRole.headhunter:
        if job.ever_confirmed_at is not None or job.created_by != current_user.id:
            _http(404, "招聘需求不存在或无权访问")
    elif current_user.role != UserRole.admin:
        _http(404, "招聘需求不存在或无权访问")
    if not can_update_job(current_user, job, db):
        _http(403, "无权修改该招聘需求")
    if job.version != payload.expected_version:
        _http(409, "招聘需求版本已变化，请刷新后重试")
    if job.status == JobStatus.closed:
        _http(409, "已关闭需求不能编辑，请新建需求")
    data = _job_data(payload)
    changed_terms = {key for key in (
        "title", "department", "description", "requirements", "salary_min", "salary_max",
        "location", "hiring_count",
    ) if key in data and getattr(job, key) != data[key]}
    try:
        for key, value in data.items():
            setattr(job, key, value)
        if changed_terms:
            job.version += 1
            job.confirmed_by = None
            job.confirmed_at = None
        db.flush()
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise


@mutation
def confirm_job(db: Session, *, current_user: User, job_id: int, expected_version: int) -> Job:
    current_user, job, _, _, _ = lock_context(db, current_user.id, job_id)
    if job is None or current_user.role != UserRole.recruiter or current_user.company_id != job.client_company_id:
        _http(404, "招聘需求不存在或无权访问")
    if current_user.company_role != CompanyRole.manager:
        _http(403, "只有客户企业主管可以确认需求")
    if job.status != JobStatus.open:
        _http(409, "仅开放中的需求可以确认")
    if job.version != expected_version:
        _http(409, "招聘需求版本已变化，请刷新后重试")
    if not _has_valid_terms(job):
        _http(409, "请补齐岗位职责和岗位要求后再确认")
    if job.confirmed_at is not None:
        _http(409, "当前需求版本已确认")
    now = datetime.now()
    job.confirmed_by, job.confirmed_at = current_user.id, now
    job.ever_confirmed_at = job.ever_confirmed_at or now
    db.commit()
    db.refresh(job)
    return job


@mutation
def change_job_status(db: Session, *, current_user: User, job_id: int,
                      expected_version: int, target_status: JobStatus, reason: str | None):
    current_user, job, _, _, _ = lock_context(db, current_user.id, job_id)
    if job is None:
        _http(404, "招聘需求不存在")
    is_admin = current_user.role == UserRole.admin
    is_manager = (current_user.role == UserRole.recruiter and
                  current_user.company_id == job.client_company_id and
                  current_user.company_role == CompanyRole.manager)
    if not current_user.enabled or not (is_admin or is_manager):
        _http(403, "只有客户企业主管可以变更需求状态")
    if job.version != expected_version:
        _http(409, "招聘需求版本已变化，请刷新后重试")
    if job.status == JobStatus.closed or target_status == job.status:
        _http(409, "需求状态不能重复或逆向变更")
    if target_status in (JobStatus.suspended, JobStatus.closed) and not (reason or "").strip():
        _http(422, "暂停或关闭需求时必须填写原因")
    if target_status == JobStatus.open:
        if job.confirmed_at is None or job.confirmed_by is None:
            _http(409, "未确认的需求不能恢复为开放状态")
    try:
        job.status = target_status
        if target_status == JobStatus.closed:
            assignments = db.query(JobAssignment).filter(
                JobAssignment.job_id == job.id,
                JobAssignment.status.in_(("invited", "active")),
            ).order_by(JobAssignment.id).with_for_update().all()
            now = datetime.now()
            for assignment in assignments:
                old = assignment.status
                assignment.status = "cancelled"
                assignment.ended_by, assignment.ended_at = current_user.id, now
                assignment.end_reason = reason.strip()
                from app.models.assignment_event import AssignmentEvent
                db.add(AssignmentEvent(
                    assignment_id=assignment.id, actor_id=current_user.id,
                    event_type="cancelled", from_status=old, to_status="cancelled",
                    job_version=job.version, reason=reason.strip(),
                    payload={"cause": "job_closed"},
                ))
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise


def list_client_options(db: Session, user: User):
    from app.models.company import Company
    from app.schemas.job import ClientCompanyOption
    if not user.enabled or user.role not in (UserRole.admin, UserRole.headhunter):
        _http(403, "当前角色无权选择代建客户企业")
    rows = db.query(Company.id, Company.name).order_by(Company.name, Company.id).all()
    return [ClientCompanyOption(id=row.id, name=row.name) for row in rows]
