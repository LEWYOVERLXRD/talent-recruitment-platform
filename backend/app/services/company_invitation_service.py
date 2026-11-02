"""客户企业通过邀请管理招聘员工归属。"""
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.company_invitation import CompanyInvitation
from app.models.user import CompanyRole, User, UserRole

INVITATION_VALID_DAYS = 7


def _lock_users(db: Session, user_ids: list[int]) -> dict[int, User]:
    rows = (
        db.query(User).filter(User.id.in_(user_ids)).order_by(User.id)
        .populate_existing().with_for_update().all()
    )
    return {row.id: row for row in rows}


def _require_company_manager(user: User) -> None:
    if not user.enabled or user.role != UserRole.recruiter or not user.company_id or user.company_role != CompanyRole.manager:
        raise HTTPException(403, "需要有效的客户企业主管权限")


def _view(invitation: CompanyInvitation) -> dict:
    status = invitation.status
    if status == "pending" and invitation.expires_at <= datetime.now():
        status = "expired"
    return {
        "id": invitation.id,
        "company_id": invitation.company_id,
        "company_name": invitation.company.name,
        "user_id": invitation.user_id,
        "username": invitation.user.username,
        "real_name": invitation.user.real_name,
        "invited_by": invitation.invited_by,
        "status": status,
        "expires_at": invitation.expires_at,
        "decided_at": invitation.decided_at,
        "created_at": invitation.created_at,
    }


def list_incoming(db: Session, user: User) -> list[dict]:
    rows = (
        db.query(CompanyInvitation)
        .options(joinedload(CompanyInvitation.company), joinedload(CompanyInvitation.user))
        .filter(CompanyInvitation.user_id == user.id)
        .order_by(CompanyInvitation.id.desc())
        .all()
    )
    return [_view(row) for row in rows]


def list_company(db: Session, user: User) -> list[dict]:
    _require_company_manager(user)
    rows = (
        db.query(CompanyInvitation)
        .options(joinedload(CompanyInvitation.company), joinedload(CompanyInvitation.user))
        .filter(CompanyInvitation.company_id == user.company_id)
        .order_by(CompanyInvitation.id.desc())
        .all()
    )
    return [_view(row) for row in rows]


def invite(db: Session, user: User, username: str) -> dict:
    _require_company_manager(user)
    target = db.query(User).filter(User.username == username.strip()).first()
    if target is None or target.role != UserRole.recruiter or not target.enabled:
        raise HTTPException(404, "未找到可邀请的有效企业招聘账号")
    locked = _lock_users(db, [user.id, target.id])
    user, target = locked[user.id], locked[target.id]
    _require_company_manager(user)
    if target.role != UserRole.recruiter or not target.enabled:
        raise HTTPException(409, "受邀账号状态已变化，请刷新后重试")
    if target.company_id is not None:
        raise HTTPException(409, "该账号已归属企业，不能接受新的企业邀请")
    pending = db.query(CompanyInvitation).filter(
        CompanyInvitation.company_id == user.company_id,
        CompanyInvitation.user_id == target.id,
        CompanyInvitation.status == "pending",
    ).populate_existing().with_for_update().first()
    if pending:
        inviter = db.get(User, pending.invited_by)
        inviter_valid = bool(inviter and inviter.enabled and inviter.role == UserRole.recruiter
                             and inviter.company_id == user.company_id and inviter.company_role == CompanyRole.manager)
        if pending.expires_at > datetime.now() and inviter_valid:
            raise HTTPException(409, "该账号已有待处理邀请")
        pending.status = "expired" if pending.expires_at <= datetime.now() else "revoked"
        pending.decided_at = datetime.now()
        db.flush()

    invitation = CompanyInvitation(
        company_id=user.company_id,
        user_id=target.id,
        invited_by=user.id,
        status="pending",
        expires_at=datetime.now() + timedelta(days=INVITATION_VALID_DAYS),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    invitation = (
        db.query(CompanyInvitation)
        .options(joinedload(CompanyInvitation.company), joinedload(CompanyInvitation.user))
        .filter(CompanyInvitation.id == invitation.id)
        .one()
    )
    return _view(invitation)


def decide(db: Session, user: User, invitation_id: int, accept: bool) -> dict:
    summary = db.query(CompanyInvitation).filter(
        CompanyInvitation.id == invitation_id, CompanyInvitation.user_id == user.id,
    ).first()
    if summary is None:
        raise HTTPException(404, "企业邀请不存在")
    locked = _lock_users(db, [user.id, summary.invited_by])
    target = locked[user.id]
    invitation = (
        db.query(CompanyInvitation)
        .filter(CompanyInvitation.id == invitation_id, CompanyInvitation.user_id == user.id)
        .populate_existing()
        .with_for_update()
        .first()
    )
    if invitation is None:
        raise HTTPException(404, "企业邀请不存在")
    if invitation.status != "pending":
        raise HTTPException(409, "该邀请已处理")
    if invitation.expires_at <= datetime.now():
        invitation.status = "expired"
        invitation.decided_at = datetime.now()
        db.commit()
        raise HTTPException(409, "该邀请已过期")
    if not target.enabled or target.role != UserRole.recruiter:
        raise HTTPException(403, "当前账号不能接受企业邀请")
    if accept and target.company_id is not None:
        raise HTTPException(409, "当前账号已归属企业，不能加入另一家企业")
    inviter = locked.get(invitation.invited_by)
    if accept and (inviter is None or not inviter.enabled or inviter.company_id != invitation.company_id
                   or inviter.company_role != CompanyRole.manager or inviter.role != UserRole.recruiter):
        raise HTTPException(409, "邀请人已不具备本企业主管权限，请联系当前主管重新邀请")

    if accept:
        target.company_id = invitation.company_id
        target.company_role = CompanyRole.staff
        invitation.status = "accepted"
    else:
        invitation.status = "declined"
    invitation.decided_at = datetime.now()
    db.commit()
    db.refresh(invitation)
    return _view(invitation)


def revoke(db: Session, user: User, invitation_id: int) -> dict:
    _require_company_manager(user)
    summary = db.query(CompanyInvitation).filter(
        CompanyInvitation.id == invitation_id, CompanyInvitation.company_id == user.company_id,
    ).first()
    if summary is None:
        raise HTTPException(404, "企业邀请不存在")
    locked = _lock_users(db, [user.id, summary.user_id, summary.invited_by])
    user = locked[user.id]
    _require_company_manager(user)
    invitation = (
        db.query(CompanyInvitation)
        .filter(CompanyInvitation.id == invitation_id, CompanyInvitation.company_id == user.company_id)
        .populate_existing()
        .with_for_update()
        .first()
    )
    if invitation is None:
        raise HTTPException(404, "企业邀请不存在")
    if invitation.status != "pending":
        raise HTTPException(409, "只有待处理邀请可以撤销")
    invitation.status = "revoked"
    invitation.decided_at = datetime.now()
    db.commit()
    db.refresh(invitation)
    return _view(invitation)
