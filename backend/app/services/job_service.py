"""招聘需求（Job）业务逻辑：双入口创建 + 数据隔离 + 权限判断（方案B 猎头核心）"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud.company import create_company, get_company_by_name
from app.crud.job import create_job as crud_create_job
from app.crud.job import get_job_by_id, list_jobs, update_job
from app.models.job import Job, JobSource, JobStatus
from app.models.user import User, UserRole
from app.schemas.job import JobCreate, JobUpdate


def can_access_job(user: User, job: Job) -> bool:
    """数据范围判断：
    admin / headhunter 可见全部需求池；recruiter 仅可见本企业需求。
    """
    if user.role in (UserRole.admin, UserRole.headhunter):
        return True
    if user.role == UserRole.recruiter:
        return job.client_company_id == user.company_id
    return False


def _new_job(
    db: Session,
    *,
    current_user: User,
    payload: JobCreate,
) -> Job:
    """创建招聘需求（双入口）"""
    # —— 客户企业归属 ——
    if current_user.role == UserRole.recruiter:
        # 企业方创建：强制归属本企业；需先有企业归属
        if current_user.company_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前招聘方账号未归属任何企业，无法发布招聘需求",
            )
        company_id = current_user.company_id
        source = JobSource.client_published
    else:
        # 猎头/管理员创建：按客户企业名称动态获取/新建
        name = (payload.client_company_name or "").strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请填写客户企业名称",
            )
        company = get_company_by_name(db, name)
        if company is None:
            company = create_company(db, name)
        company_id = company.id
        source = JobSource.headhunter_created

    return crud_create_job(
        db,
        title=payload.title,
        client_company_id=company_id,
        created_by=current_user.id,
        source=source,
        department=payload.department,
        description=payload.description,
        requirements=payload.requirements,
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        location=payload.location,
        contact_person=payload.contact_person,
        contact_info=payload.contact_info,
        hiring_count=payload.hiring_count,
        priority=payload.priority,
    )


def new_job(db: Session, *, current_user: User, payload: JobCreate) -> Job:
    if current_user.role not in (UserRole.recruiter, UserRole.headhunter, UserRole.admin):
        raise HTTPException(status_code=403, detail="当前角色无权创建招聘需求")
    return _new_job(db, current_user=current_user, payload=payload)


def list_job_page(
    db: Session,
    *,
    current_user: User,
    status_filter: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[int, list[Job]]:
    """按角色做数据隔离的分页查询。

    - recruiter：仅本企业需求
    - headhunter / admin：全部需求池（需求池模式）
    - jobseeker / 其它：403
    """
    if current_user.role == UserRole.recruiter:
        company_id = current_user.company_id
    elif current_user.role in (UserRole.headhunter, UserRole.admin):
        company_id = None
    else:
        raise HTTPException(status_code=403, detail="当前角色无权查看招聘需求")

    status_obj = None
    if status_filter:
        try:
            status_obj = JobStatus(status_filter)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的需求状态")

    page = max(1, page)
    size = max(1, min(100, size))
    return list_jobs(
        db,
        company_id=company_id,
        status=status_obj,
        keyword=keyword,
        offset=(page - 1) * size,
        limit=size,
    )


def get_job_detail(db: Session, *, current_user: User, job_id: int) -> Job:
    job = get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="招聘需求不存在")
    if not can_access_job(current_user, job):
        raise HTTPException(status_code=403, detail="无权访问该招聘需求")
    return job


def patch_job(
    db: Session, *, current_user: User, job_id: int, payload: JobUpdate
) -> Job:
    job = get_job_detail(db, current_user=current_user, job_id=job_id)
    # 更新仅允许更新非关键业务字段；客户企业归属不可在此修改
    data = payload.model_dump(exclude_unset=True)
    data.pop("client_company_id", None)
    return update_job(db, job, data)