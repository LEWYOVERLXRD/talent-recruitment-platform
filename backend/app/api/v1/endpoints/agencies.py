"""猎头机构接口；角色与成员权限由服务层再次校验。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.agency import (
    AgencyContext, AgencyCreate, AgencyList, AgencyOut, AgencyStatusUpdate,
    InvitationDecision, MemberInvite, MemberLeave, MemberOut, MemberRoleUpdate,
)
from app.services import agency_service as service

router = APIRouter(prefix="/agencies", tags=["猎头机构"])


@router.get("/context", response_model=AgencyContext)
def context(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.get_context(db, user)


@router.get("", response_model=AgencyList)
def list_agencies(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_agencies(db, user, page, size)


@router.post("", response_model=AgencyOut, status_code=201)
def create(payload: AgencyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.create_agency(db, user, payload)


@router.patch("/{agency_id}/status", response_model=AgencyOut)
def set_status(agency_id: int, payload: AgencyStatusUpdate,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.set_agency_status(db, user, agency_id, payload)


@router.get("/{agency_id}/members", response_model=list[MemberOut])
def members(agency_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.list_members(db, user, agency_id)


@router.post("/{agency_id}/invitations", response_model=MemberOut, status_code=201)
def invite(agency_id: int, payload: MemberInvite,
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.invite_member(db, user, agency_id, payload)


@router.post("/{agency_id}/members/{member_id}/decision", response_model=MemberOut)
def decide(agency_id: int, member_id: int, payload: InvitationDecision,
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.decide_invitation(db, user, agency_id, member_id, payload)


@router.patch("/{agency_id}/members/{member_id}/role", response_model=MemberOut)
def set_role(agency_id: int, member_id: int, payload: MemberRoleUpdate,
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.change_member_role(db, user, agency_id, member_id, payload)


@router.post("/{agency_id}/members/{member_id}/leave", response_model=MemberOut)
def leave(agency_id: int, member_id: int, payload: MemberLeave,
          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.leave_member(db, user, agency_id, member_id, payload)


@router.post("/{agency_id}/members/{member_id}/cancel", response_model=MemberOut)
def cancel(agency_id: int, member_id: int,
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.cancel_invitation(db, user, agency_id, member_id)
