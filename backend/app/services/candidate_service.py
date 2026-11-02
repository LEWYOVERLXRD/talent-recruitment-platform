"""候选人（Candidate）业务逻辑：个人/机构归属隔离与当前权限（猎头人才库）"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.candidate import (
    create_candidate as crud_create_candidate,
    get_candidate_by_id,
    list_candidates,
    update_candidate,
)
from app.models.candidate import Candidate, CandidateSource
from app.models.user import User, UserRole
from app.schemas.candidate import CandidateCreate, CandidateUpdate
from app.services.candidate_access import can_access_candidate, candidate_visibility
from app.services.candidate_ownership import creation_identity, lock_candidate_for_write
from app.services.agency_service import mutation


@mutation
def new_candidate(
    db: Session, *, current_user: User, payload: CandidateCreate
) -> Candidate:
    """创建候选人（仅 admin / headhunter 可录入人才库）"""
    provider, owner_id = creation_identity(db, current_user, payload)

    source = payload.source or CandidateSource.manual
    return crud_create_candidate(
        db,
        name=payload.name,
        created_by=current_user.id,
        source=source,
        provider_id=provider.id,
        owner_user_id=owner_id,
        gender=payload.gender,
        phone=payload.phone,
        email=payload.email,
        current_company=payload.current_company,
        current_position=payload.current_position,
        years_of_experience=payload.years_of_experience,
        education=payload.education,
        expected_salary=payload.expected_salary,
        expected_location=payload.expected_location,
    )


def list_candidate_page(
    db: Session,
    *,
    current_user: User,
    keyword: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[int, list[Candidate]]:
    """按角色做归属隔离的分页查询。

    - admin：全部人才库
    - headhunter：个人档案或有当前机构权限的档案
    - jobseeker：仅自己的自助档案
    - 其它角色：403
    """
    if not current_user.enabled or current_user.role not in (UserRole.admin, UserRole.headhunter, UserRole.jobseeker):
        raise HTTPException(status_code=403, detail="当前角色无权查看候选人")

    page = max(1, page)
    size = max(1, min(100, size))
    return list_candidates(
        db,
        visibility=candidate_visibility(current_user),
        keyword=keyword,
        offset=(page - 1) * size,
        limit=size,
    )


def get_candidate_detail(
    db: Session, *, current_user: User, candidate_id: int
) -> Candidate:
    candidate = get_candidate_by_id(db, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    if not can_access_candidate(db, current_user, candidate):
        raise HTTPException(status_code=403, detail="无权访问该候选人")
    return candidate


@mutation
def patch_candidate(
    db: Session, *, current_user: User, candidate_id: int, payload: CandidateUpdate
) -> Candidate:
    candidate = lock_candidate_for_write(db, current_user, candidate_id)
    # 普通资料修改不能注入归属、负责人或历史建档人。
    data = payload.model_dump(exclude_unset=True)
    if current_user.role == UserRole.jobseeker:
        data.pop("source", None)
    if any(data.get(key) is None for key in ("name", "source") if key in data):
        raise HTTPException(422, "姓名和来源不能清空")
    return update_candidate(db, candidate, data)
