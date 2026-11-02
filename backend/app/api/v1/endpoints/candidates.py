"""候选人（Candidate）接口模块（猎头人才库）"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.user import User, UserRole
from app.schemas.candidate import (
    CandidateCreate,
    CandidateListResponse,
    CandidateOut,
    CandidateUpdate,
    CandidateTransfer,
)
from app.services import candidate_service
from app.services.candidate_ownership import transfer_candidate

router = APIRouter(prefix="/candidates", tags=["候选人"])

# 允许操作候选人人才库的平台角色：猎头 + 平台管理员
_CANDIDATE_ROLES = (
    UserRole.headhunter,
    UserRole.admin,
    UserRole.jobseeker,
)


@router.post("", response_model=CandidateOut, summary="创建候选人（猎头录入人才库）")
def create_candidate(
    payload: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_CANDIDATE_ROLES)),
):
    return candidate_service.new_candidate(db, current_user=current_user, payload=payload)


@router.get("", response_model=CandidateListResponse, summary="候选人分页列表")
def list_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_CANDIDATE_ROLES)),
    keyword: str | None = Query(None, description="按姓名/公司/职位关键字检索"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    total, items = candidate_service.list_candidate_page(
        db, current_user=current_user, keyword=keyword, page=page, size=size
    )
    return CandidateListResponse(total=total, items=items)


@router.get("/{candidate_id}", response_model=CandidateOut, summary="候选人详情")
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_CANDIDATE_ROLES)),
):
    return candidate_service.get_candidate_detail(
        db, current_user=current_user, candidate_id=candidate_id
    )


@router.patch("/{candidate_id}", response_model=CandidateOut, summary="更新候选人")
def update_candidate(
    candidate_id: int,
    payload: CandidateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_CANDIDATE_ROLES)),
):
    return candidate_service.patch_candidate(
        db, current_user=current_user, candidate_id=candidate_id, payload=payload
    )


@router.post("/{candidate_id}/transfer", response_model=CandidateOut, summary="同机构转派负责人")
def transfer(candidate_id: int, payload: CandidateTransfer,
             db: Session = Depends(get_db),
             current_user: User = Depends(require_role(*_CANDIDATE_ROLES))):
    return transfer_candidate(db, current_user, candidate_id, payload.owner_user_id)
