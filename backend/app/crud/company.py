"""企业相关数据库操作（CRUD）"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.user import User, UserRole


def get_company_by_name(db: Session, name: str) -> Optional[Company]:
    """按企业名称查企业"""
    return db.query(Company).filter(Company.name == name).first()


def get_company_by_id(db: Session, company_id: int) -> Optional[Company]:
    """按 id 查企业"""
    return db.query(Company).filter(Company.id == company_id).first()


def create_company(db: Session, name: str) -> Company:
    """创建企业"""
    company = Company(name=name)
    db.add(company)
    db.commit()
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