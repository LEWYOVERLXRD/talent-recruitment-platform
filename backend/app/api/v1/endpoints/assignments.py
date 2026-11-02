"""客户定向邀请与猎头需求承接 API。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models import User, UserRole
from app.schemas.job_assignment import AssignmentAction, AssignmentEventOut, AssignmentListItem, AssignmentTransfer, ProviderOption
from app.services import assignment_service

router = APIRouter(prefix="/assignments", tags=["需求承接"])
provider_router = APIRouter(prefix="/service-providers", tags=["需求承接"])


@provider_router.get("", response_model=list[ProviderOption], summary="客户主管选择定向邀请主体")
def list_service_providers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return assignment_service.provider_options(db, current_user)


@router.get("", response_model=list[AssignmentListItem], summary="我的需求承接")
def list_assignments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return assignment_service.list_assignments(db, current_user)


@router.get("/{assignment_id}", response_model=AssignmentListItem, summary="需求承接详情")
def get_assignment(assignment_id: int, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    return assignment_service.get_assignment(db, current_user, assignment_id)


@router.get("/{assignment_id}/events", response_model=list[AssignmentEventOut], summary="需求承接操作历史")
def get_assignment_events(assignment_id: int, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    return assignment_service.list_assignment_events(db, current_user, assignment_id)


@router.post("/{assignment_id}/accept", response_model=AssignmentListItem, summary="接受定向邀请")
def accept(assignment_id: int, payload: AssignmentAction,
           db: Session = Depends(get_db), current_user: User = Depends(require_role(UserRole.headhunter))):
    return assignment_service.decide_invitation(
        db, current_user, assignment_id, expected_round=payload.expected_round,
        accept=True,
    )


@router.post("/{assignment_id}/decline", response_model=AssignmentListItem, summary="拒绝定向邀请")
def decline(assignment_id: int, payload: AssignmentAction,
            db: Session = Depends(get_db), current_user: User = Depends(require_role(UserRole.headhunter))):
    return assignment_service.decide_invitation(
        db, current_user, assignment_id, expected_round=payload.expected_round,
        accept=False, reason=payload.reason,
    )


@router.post("/{assignment_id}/cancel", response_model=AssignmentListItem, summary="撤销邀请或终止承接")
def cancel(assignment_id: int, payload: AssignmentAction,
           db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return assignment_service.end_assignment(
        db, current_user, assignment_id, expected_round=payload.expected_round,
        complete=False, reason=payload.reason,
    )


@router.post("/{assignment_id}/complete", response_model=AssignmentListItem, summary="确认承接完成")
def complete(assignment_id: int, payload: AssignmentAction,
             db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return assignment_service.end_assignment(
        db, current_user, assignment_id, expected_round=payload.expected_round,
        complete=True, reason=payload.reason,
    )


@router.post("/{assignment_id}/owner", response_model=AssignmentListItem, summary="机构主管分配任务负责人")
def transfer_owner(assignment_id: int, payload: AssignmentTransfer,
                   db: Session = Depends(get_db), current_user: User = Depends(require_role(UserRole.headhunter))):
    return assignment_service.transfer_owner(
        db, current_user, assignment_id, expected_round=payload.expected_round,
        expected_owner_user_id=payload.expected_owner_user_id,
        owner_user_id=payload.owner_user_id,
    )
