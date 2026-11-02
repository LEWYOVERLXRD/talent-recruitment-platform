"""企业相关数据库操作（CRUD）"""
from typing import Optional

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.user import CompanyRole, User, UserRole


def get_company_by_name(db: Session, name: str) -> Optional[Company]:
    """按企业名称查企业"""
    return db.query(Company).filter(Company.name == name).first()


def get_company_by_id(db: Session, company_id: int) -> Optional[Company]:
    """按 id 查企业"""
    return db.query(Company).filter(Company.id == company_id).first()


def create_company(db: Session, name: str, *, commit: bool = True) -> Company:
    """创建企业"""
    company = Company(name=name)
    db.add(company)
    if commit:
        db.commit()
    else:
        db.flush()
    db.refresh(company)
    return company


def list_company_members(db: Session, company_id: int) -> list[User]:
    """查询某企业的全部招聘方成员"""
    return (
        db.query(User)
        .filter(User.company_id == company_id, User.role == UserRole.recruiter)
        .order_by(User.id)
        .all()
    )


def get_company_member(db: Session, company_id: int, user_id: int) -> Optional[User]:
    """查询某企业下的指定成员（用于权限校验）"""
    return (
        db.query(User)
        .filter(
            User.id == user_id,
            User.company_id == company_id,
            User.role == UserRole.recruiter,
        )
        .first()
    )


def _company_admin_query(db: Session):
    """聚合成员后关联企业，避免逐企业读取成员及空企业被遗漏。"""
    counts = (
        db.query(
            User.company_id,
            func.count(User.id).label("member_count"),
            func.sum(case((User.company_role == CompanyRole.manager, 1), else_=0)).label("manager_count"),
            func.sum(case(((User.company_role == CompanyRole.manager) & User.enabled.is_(True), 1), else_=0)).label("enabled_manager_count"),
        )
        .filter(User.role == UserRole.recruiter)
        .group_by(User.company_id)
        .subquery()
    )
    return db.query(
        Company.id, Company.name, Company.created_at,
        func.coalesce(counts.c.member_count, 0).label("member_count"),
        func.coalesce(counts.c.manager_count, 0).label("manager_count"),
        func.coalesce(counts.c.enabled_manager_count, 0).label("enabled_manager_count"),
    ).outerjoin(counts, Company.id == counts.c.company_id)


def list_admin_companies(db: Session, *, page: int, size: int, keyword: Optional[str] = None):
    query = _company_admin_query(db)
    if keyword and keyword.strip():
        query = query.filter(Company.name.contains(keyword.strip(), autoescape=True))
    total = query.count()
    items = query.order_by(Company.id.desc()).offset((page - 1) * size).limit(size).all()
    return items, total


def get_admin_company(db: Session, company_id: int):
    return _company_admin_query(db).filter(Company.id == company_id).first()


def list_admin_company_members(
    db: Session, company_id: int, *, page: int, size: int,
    keyword: Optional[str] = None, company_role: Optional[CompanyRole] = None,
    enabled: Optional[bool] = None,
):
    query = db.query(User).filter(User.company_id == company_id, User.role == UserRole.recruiter)
    if keyword and keyword.strip():
        term = keyword.strip()
        query = query.filter(or_(User.username.contains(term, autoescape=True), User.real_name.contains(term, autoescape=True)))
    if company_role is not None:
        query = query.filter(User.company_role == company_role)
    if enabled is not None:
        query = query.filter(User.enabled == enabled)
    total = query.count()
    return query.order_by(User.id).offset((page - 1) * size).limit(size).all(), total
