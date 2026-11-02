"""候选人（Candidate）数据库操作"""
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateSource


def get_candidate_by_id(db: Session, candidate_id: int) -> Optional[Candidate]:
    """按 id 查候选人"""
    return db.query(Candidate).filter(Candidate.id == candidate_id).first()


def create_candidate(
    db: Session,
    *,
    name: str,
    created_by: int,
    source: CandidateSource,
    provider_id: int,
    owner_user_id: int,
    gender: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    current_company: Optional[str] = None,
    current_position: Optional[str] = None,
    years_of_experience: Optional[int] = None,
    education: Optional[str] = None,
    expected_salary: Optional[str] = None,
    expected_location: Optional[str] = None,
) -> Candidate:
    """创建候选人，事务由服务层提交。"""
    candidate = Candidate(
        name=name,
        gender=gender,
        phone=phone,
        email=email,
        current_company=current_company,
        current_position=current_position,
        years_of_experience=years_of_experience,
        education=education,
        expected_salary=expected_salary,
        expected_location=expected_location,
        source=source,
        created_by=created_by,
        provider_id=provider_id,
        owner_user_id=owner_user_id,
    )
    db.add(candidate)
    db.flush()
    return candidate


def update_candidate(db: Session, candidate: Candidate, data: dict) -> Candidate:
    """按字段字典更新候选人（仅更新传入字段）"""
    for key, value in data.items():
        setattr(candidate, key, value)
    db.flush()
    return candidate


def list_candidates(
    db: Session,
    *,
    visibility,
    keyword: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[int, list[Candidate]]:
    """分页查询候选人（支持按归属顾问、姓名/公司/职位关键字过滤）"""
    query = db.query(Candidate).filter(visibility)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            or_(
                Candidate.name.like(kw),
                Candidate.current_company.like(kw),
                Candidate.current_position.like(kw),
            )
        )
    total = query.count()
    items = (
        query.order_by(Candidate.created_at.desc(), Candidate.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return total, items
