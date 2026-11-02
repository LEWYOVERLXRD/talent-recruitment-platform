"""AI 人岗匹配接口模块"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.user import User, UserRole
from app.schemas.match_analysis import (
    MatchAnalysisListResponse,
    MatchAnalysisOut,
    MatchCreateRequest,
)
from app.services import match_service

router = APIRouter(prefix="/matches", tags=["AI人岗匹配"])

# 列表和详情允许猎头与管理员核验；生成新匹配仅允许猎头。
_MATCH_ROLES = (
    UserRole.headhunter,
    UserRole.admin,
)


@router.post("", response_model=MatchAnalysisOut, summary="执行 AI 人岗匹配")
def run_match(
    payload: MatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.headhunter)),
):
    return match_service.run_match(db, current_user=current_user, payload=payload)


@router.get("", response_model=MatchAnalysisListResponse, summary="匹配结果分页列表")
def list_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MATCH_ROLES)),
    job_id: int | None = Query(None, description="按招聘需求过滤"),
    candidate_id: int | None = Query(None, description="按候选人过滤"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    total, items = match_service.list_match_page(
        db,
        current_user=current_user,
        job_id=job_id,
        candidate_id=candidate_id,
        page=page,
        size=size,
    )
    return MatchAnalysisListResponse(total=total, items=items)


@router.get("/{match_id}", response_model=MatchAnalysisOut, summary="匹配结果详情")
def get_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_MATCH_ROLES)),
):
    return match_service.get_match_detail(
        db, current_user=current_user, match_id=match_id
    )
