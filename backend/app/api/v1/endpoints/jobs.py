"""招聘需求（Job）接口模块（方案B：猎头核心）"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.user import User, UserRole
from app.schemas.job import (
    JobCreate,
    JobListResponse,
    JobOut,
    JobUpdate,
)
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["招聘需求"])

# 允许操作招聘需求模块的平台角色
_JOB_ROLES = (
    UserRole.recruiter,
    UserRole.headhunter,
    UserRole.admin,
)


@router.post("", response_model=JobOut, summary="创建招聘需求（双入口）")
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_JOB_ROLES)),
):
    return job_service.new_job(db, current_user=current_user, payload=payload)


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
    return JobListResponse(total=total, items=items)


@router.get("/{job_id}", response_model=JobOut, summary="招聘需求详情")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_JOB_ROLES)),
):
    return job_service.get_job_detail(db, current_user=current_user, job_id=job_id)


@router.patch("/{job_id}", response_model=JobOut, summary="更新招聘需求")
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_JOB_ROLES)),
):
    return job_service.patch_job(
        db, current_user=current_user, job_id=job_id, payload=payload
    )