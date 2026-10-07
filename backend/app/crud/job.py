"""招聘需求（Job）数据库操作"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.job import Job, JobSource, JobStatus


def get_job_by_id(db: Session, job_id: int) -> Optional[Job]:
    """按 id 查招聘需求"""
    return db.query(Job).filter(Job.id == job_id).first()


def create_job(
    db: Session,
    *,
    title: str,
    client_company_id: int,
    created_by: int,
    source: JobSource,
    department: Optional[str] = None,
    description: Optional[str] = None,
    requirements: Optional[str] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    location: Optional[str] = None,
    contact_person: Optional[str] = None,
    contact_info: Optional[str] = None,
    hiring_count: Optional[int] = None,
    priority: Optional[str] = None,
) -> Job:
    """创建招聘需求"""
    job = Job(
        title=title,
        department=department,
        description=description,
        requirements=requirements,
        salary_min=salary_min,
        salary_max=salary_max,
        location=location,
        client_company_id=client_company_id,
        source=source,
        contact_person=contact_person,
        contact_info=contact_info,
        hiring_count=hiring_count,
        priority=priority,
        created_by=created_by,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job(db: Session, job: Job, data: dict) -> Job:
    """按字段字典更新招聘需求（仅更新传入字段）"""
    for key, value in data.items():
        setattr(job, key, value)
    db.commit()
    db.refresh(job)
    return job


def list_jobs(
    db: Session,
    *,
    company_id: Optional[int] = None,
    creator_id: Optional[int] = None,
    status: Optional[JobStatus] = None,
    keyword: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[int, list[Job]]:
    """分页查询招聘需求（支持按企业、建档人、状态、关键字过滤）"""
    query = db.query(Job)
    if company_id is not None:
        query = query.filter(Job.client_company_id == company_id)
    if creator_id is not None:
        query = query.filter(Job.created_by == creator_id)
    if status is not None:
        query = query.filter(Job.status == status)
    if keyword:
        query = query.filter(Job.title.like(f"%{keyword}%"))
    total = query.count()
    items = (
        query.order_by(Job.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return total, items