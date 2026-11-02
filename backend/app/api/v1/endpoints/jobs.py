"""招聘需求（Job）接口模块（方案B：猎头核心）"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User, UserRole
from app.schemas.job import (
    JobCreate,
    JobConfirm,
    JobListResponse,
    JobOut,
    JobProfileOut,
    JobStatusChange,
    JobUpdate,
)
from app.services import job_service
from app.schemas.job_assignment import AssignmentListItem, InvitationCreate
from app.services.assignment_service import invite_provider

router = APIRouter(prefix="/jobs", tags=["招聘需求"])

# 允许操作招聘需求模块的平台角色
_JOB_ROLES = (
    UserRole.recruiter,
    UserRole.headhunter,
    UserRole.admin,
    UserRole.jobseeker,
)


def _out(db, user, job):
    from app.services.job_service import can_access_active_job, can_view_job_contact
    data = {field: getattr(job, field) for field in JobOut.model_fields if hasattr(job, field)}
    data["client_company_name"] = job.client_company_name
    if not can_view_job_contact(user, job, db):
        data["contact_person"] = None
        data["contact_info"] = None
    data["has_current_authorization"] = (
        user.role == UserRole.admin or
        (user.role == UserRole.recruiter and user.company_id == job.client_company_id) or
        (user.role == UserRole.headhunter and can_access_active_job(user, job, db))
    )
    if user.role == UserRole.jobseeker:
        from app.services.public_jobs import public_receivers
        data["receivers"] = public_receivers(db, job.id)
    return data


@router.post("", response_model=JobOut, summary="创建招聘需求（双入口）")
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _out(db, current_user, job_service.new_job(db, current_user=current_user, payload=payload))


@router.get("", response_model=JobListResponse, summary="招聘需求分页列表")
def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_JOB_ROLES)),
    status: str | None = Query(None, description="状态过滤 open/suspended/closed"),
    keyword: str | None = Query(None, description="按标题关键字检索"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    total, items = job_service.list_job_page(
        db,
        current_user=current_user,
        status_filter=status,
        keyword=keyword,
        page=page,
        size=size,
    )
    return JobListResponse(total=total, items=[_out(db, current_user, item) for item in items])


@router.get("/{job_id}", response_model=JobOut, summary="招聘需求详情")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_JOB_ROLES)),
):
    return _out(db, current_user, job_service.get_job_detail(db, current_user=current_user, job_id=job_id))


@router.patch("/{job_id}", response_model=JobOut, summary="更新招聘需求")
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.recruiter, UserRole.headhunter, UserRole.admin)),
):
    return _out(db, current_user, job_service.patch_job(
        db, current_user=current_user, job_id=job_id, payload=payload
    ))


@router.get("/{job_id}/profile", response_model=JobProfileOut, summary="生成需求的原始岗位资料")
def get_profile(job_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(require_role(*_JOB_ROLES))):
    return job_service.get_job_profile(db, current_user=current_user, job_id=job_id)


@router.post("/{job_id}/confirm", response_model=JobOut, summary="客户主管确认招聘需求")
def confirm_job(job_id: int, payload: JobConfirm,
                db: Session = Depends(get_db),
                current_user: User = Depends(require_role(UserRole.recruiter))):
    return _out(db, current_user, job_service.confirm_job(
        db, current_user=current_user, job_id=job_id, expected_version=payload.expected_version
    ))


@router.post("/{job_id}/status", response_model=JobOut, summary="客户主管变更需求状态")
def change_job_status(job_id: int, payload: JobStatusChange,
                      db: Session = Depends(get_db),
                      current_user: User = Depends(require_role(UserRole.recruiter, UserRole.admin))):
    return _out(db, current_user, job_service.change_job_status(
        db, current_user=current_user, job_id=job_id, expected_version=payload.expected_version,
        target_status=payload.status, reason=payload.reason,
    ))


@router.post("/{job_id}/invitations", response_model=AssignmentListItem, summary="向个人猎头或猎头机构定向邀请")
def invite(job_id: int, payload: InvitationCreate, db: Session = Depends(get_db),
           current_user: User = Depends(require_role(UserRole.recruiter))):
    return invite_provider(db, current_user, job_id, payload.provider_kind,
                           payload.target_id, payload.expected_version)
