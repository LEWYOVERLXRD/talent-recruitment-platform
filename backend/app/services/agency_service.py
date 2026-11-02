"""机构身份与成员流程；服务层持有事务，数据库约束兜底并发身份冲突。"""
from datetime import datetime
from functools import wraps

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Agency, AgencyMember, AssignmentEvent, Candidate, Job, JobAssignment, ServiceProvider, User, UserRole


def mutation(function):
    @wraps(function)
    def wrapped(db: Session, *args, **kwargs):
        try:
            result = function(db, *args, **kwargs)
            db.commit()
            return result
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "身份或数据已发生变化，请刷新后重试") from None
        except Exception:
            db.rollback()
            raise
    return wrapped


def require_enabled(user):
    if not user.enabled:
        raise HTTPException(403, "账号已停用")


def active_member(db, user_id, agency_id=None, *, lock=False):
    query = db.query(AgencyMember).filter(
        AgencyMember.user_id == user_id, AgencyMember.status == "active"
    )
    if agency_id is not None:
        query = query.filter(AgencyMember.agency_id == agency_id)
    if lock:
        query = query.populate_existing().with_for_update()
    return query.first()


def locked_agency(db, agency_id):
    agency = db.query(Agency).filter(Agency.id == agency_id).populate_existing().with_for_update().first()
    if agency is None:
        raise HTTPException(404, "机构不存在")
    return agency


def lock_users(db, ids):
    return {u.id: u for u in db.query(User).filter(User.id.in_(set(ids))).order_by(
        User.id
    ).populate_existing().with_for_update().all()}


def require_manager(db, user, agency):
    require_enabled(user)
    if user.role == UserRole.admin:
        return
    member = active_member(db, user.id, agency.id, lock=True)
    if (user.role != UserRole.headhunter or agency.status != "active"
            or member is None or member.role != "manager"):
        raise HTTPException(403, "需要本机构主管权限")


def require_hunter(user):
    if user is None or user.role != UserRole.headhunter or not user.enabled:
        raise HTTPException(409, "目标必须是有效猎头账号")


def provider_for_user(db, user):
    provider = db.query(ServiceProvider).filter(ServiceProvider.user_id == user.id).first()
    if provider is None:
        provider = ServiceProvider(kind="individual", user_id=user.id)
        db.add(provider)
        db.flush()
    return provider


def member_output(db, member):
    user = db.get(User, member.user_id)
    return {
        "id": member.id, "agency_id": member.agency_id, "user_id": member.user_id,
        "role": member.role, "status": member.status,
        "joined_at": member.joined_at, "left_at": member.left_at,
        "username": user.username if user else None,
        "real_name": user.real_name if user else None,
        "enabled": user.enabled if user else None,
    }


def get_context(db, user):
    require_enabled(user)
    if user.role not in (UserRole.headhunter, UserRole.admin):
        raise HTTPException(403, "当前角色无机构入口")
    member = active_member(db, user.id)
    agency = db.get(Agency, member.agency_id) if member else None
    invitations = db.query(AgencyMember).join(Agency, Agency.id == AgencyMember.agency_id).filter(
        AgencyMember.user_id == user.id, AgencyMember.status == "invited", Agency.status == "active"
    ).order_by(AgencyMember.id).all()
    return {"agency": agency, "membership": member_output(db, member) if member else None,
            "invitations": [member_output(db, row) for row in invitations]}


def list_agencies(db, user, page, size):
    require_enabled(user)
    if user.role != UserRole.admin:
        raise HTTPException(403, "需要平台管理员权限")
    query = db.query(Agency)
    return {"total": query.count(), "items": query.order_by(Agency.id).offset((page - 1) * size).limit(size).all()}


@mutation
def create_agency(db, user, payload):
    require_enabled(user)
    if user.role != UserRole.admin:
        raise HTTPException(403, "机构需由平台核验创建")
    manager = lock_users(db, [payload.manager_user_id]).get(payload.manager_user_id)
    require_hunter(manager)
    if active_member(db, manager.id, lock=True):
        raise HTTPException(409, "该猎头已有有效机构")
    agency = Agency(name=payload.name, created_by=user.id)
    db.add(agency)
    db.flush()
    db.add(ServiceProvider(kind="agency", agency_id=agency.id))
    db.add(AgencyMember(agency_id=agency.id, user_id=manager.id, role="manager", status="active",
                        invited_by=user.id, joined_at=datetime.now()))
    db.flush()
    return agency


@mutation
def set_agency_status(db, user, agency_id, payload):
    require_enabled(user)
    if user.role != UserRole.admin:
        raise HTTPException(403, "需要平台管理员权限")
    agency = locked_agency(db, agency_id)
    agency.status = payload.status
    return agency


def list_members(db, user, agency_id):
    require_enabled(user)
    agency = db.get(Agency, agency_id)
    if agency is None:
        raise HTTPException(404, "机构不存在")
    member = active_member(db, user.id, agency_id)
    if user.role != UserRole.admin and (
        user.role != UserRole.headhunter or not member or agency.status != "active"
    ):
        raise HTTPException(403, "无权查看该机构成员")
    query = db.query(AgencyMember).filter(AgencyMember.agency_id == agency_id)
    if user.role != UserRole.admin and member.role != "manager":
        query = query.filter(AgencyMember.status == "active")
    return [member_output(db, row) for row in query.order_by(AgencyMember.id).all()]


@mutation
def invite_member(db, user, agency_id, payload):
    agency = locked_agency(db, agency_id)
    require_manager(db, user, agency)
    if agency.status != "active":
        raise HTTPException(409, "机构已停用")
    target = db.query(User).filter(User.username == payload.username.strip()).first()
    if target is None:
        raise HTTPException(404, "目标账号不存在")
    target = lock_users(db, [target.id])[target.id]
    require_hunter(target)
    if active_member(db, target.id, lock=True):
        raise HTTPException(409, "目标已有有效机构")
    invitation = AgencyMember(agency_id=agency_id, user_id=target.id, role=payload.role,
                              status="invited", invited_by=user.id)
    db.add(invitation)
    db.flush()
    return member_output(db, invitation)


def member_in_agency(db, agency_id, member_id):
    member = db.query(AgencyMember).filter(
        AgencyMember.id == member_id, AgencyMember.agency_id == agency_id
    ).populate_existing().with_for_update().first()
    if member is None:
        raise HTTPException(404, "成员记录不存在")
    return member


@mutation
def decide_invitation(db, user, agency_id, member_id, payload):
    agency = locked_agency(db, agency_id)
    current = lock_users(db, [user.id]).get(user.id)
    require_hunter(current)
    member = member_in_agency(db, agency_id, member_id)
    if member.user_id != user.id:
        raise HTTPException(403, "只能处理本人邀请")
    if member.status != "invited" or agency.status != "active":
        raise HTTPException(409, "邀请已失效")
    if payload.accept:
        if active_member(db, user.id, lock=True):
            raise HTTPException(409, "已有有效机构，不能重复加入")
        member.status = "active"
        member.joined_at = datetime.now()
    else:
        member.status = "declined"
    db.flush()
    return member_output(db, member)


def protect_last_manager(db, agency_id, member):
    target = db.get(User, member.user_id)
    if member.role != "manager" or not target.enabled:
        return
    others = db.query(AgencyMember.id).join(User, User.id == AgencyMember.user_id).filter(
        AgencyMember.agency_id == agency_id, AgencyMember.status == "active",
        AgencyMember.role == "manager", AgencyMember.id != member.id, User.enabled.is_(True),
    ).with_for_update().first()
    if others is None:
        raise HTTPException(409, "不能移除最后一位有效主管，请先任命其他主管")


@mutation
def change_member_role(db, user, agency_id, member_id, payload):
    agency = locked_agency(db, agency_id)
    require_manager(db, user, agency)
    member = member_in_agency(db, agency_id, member_id)
    lock_users(db, [member.user_id])
    if member.status != "active":
        raise HTTPException(409, "只能调整有效成员角色")
    if payload.role == "manager":
        require_hunter(db.get(User, member.user_id))
    elif member.role == "manager":
        protect_last_manager(db, agency_id, member)
    member.role = payload.role
    db.flush()
    return member_output(db, member)


@mutation
def leave_member(db, user, agency_id, member_id, payload):
    agency = locked_agency(db, agency_id)
    require_enabled(user)
    member = member_in_agency(db, agency_id, member_id)
    if member.user_id != user.id:
        require_manager(db, user, agency)
    elif agency.status != "active":
        raise HTTPException(409, "停用机构由平台核验处理退出")
    users = lock_users(db, [member.user_id] + ([payload.transfer_to_user_id] if payload.transfer_to_user_id else []))
    if member.status != "active":
        raise HTTPException(409, "该成员不是有效成员")
    protect_last_manager(db, agency_id, member)
    provider = db.query(ServiceProvider).filter(ServiceProvider.agency_id == agency_id).one()
    assignment_job_ids = [row[0] for row in db.query(JobAssignment.job_id).filter(
        JobAssignment.provider_id == provider.id,
        JobAssignment.owner_user_id == member.user_id,
    ).distinct().order_by(JobAssignment.job_id).all()]
    if assignment_job_ids:
        db.query(Job).filter(Job.id.in_(assignment_job_ids)).order_by(Job.id).populate_existing().with_for_update().all()
    assignments = db.query(JobAssignment).filter(
        JobAssignment.provider_id == provider.id,
        JobAssignment.owner_user_id == member.user_id,
    ).order_by(JobAssignment.job_id, JobAssignment.id).populate_existing().with_for_update().all()
    candidates = db.query(Candidate).filter(
        Candidate.provider_id == provider.id, Candidate.owner_user_id == member.user_id
    ).order_by(Candidate.id).with_for_update().all()
    if candidates or assignments:
        target_id = payload.transfer_to_user_id
        if target_id == member.user_id or target_id is None:
            raise HTTPException(409, "退出前需指定有效同机构成员承接候选人与任务")
        require_hunter(users.get(target_id))
        if active_member(db, target_id, agency_id, lock=True) is None:
            raise HTTPException(409, "移交目标不是本机构有效成员")
        for candidate in candidates:
            candidate.owner_user_id = target_id
        for assignment in assignments:
            old_owner = assignment.owner_user_id
            assignment.owner_user_id = target_id
            db.add(AssignmentEvent(
                assignment_id=assignment.id, actor_id=user.id,
                event_type="reassigned", from_status=assignment.status,
                to_status=assignment.status, job_version=assignment.job_version,
                payload={"reason": "agency_member_exit", "from_owner_user_id": old_owner,
                         "to_owner_user_id": target_id},
            ))
    member.status = "left"
    member.left_at = datetime.now()
    db.flush()
    return member_output(db, member)


@mutation
def cancel_invitation(db, user, agency_id, member_id):
    agency = locked_agency(db, agency_id)
    require_manager(db, user, agency)
    member = member_in_agency(db, agency_id, member_id)
    if member.status != "invited":
        raise HTTPException(409, "只能取消待处理邀请")
    member.status = "cancelled"
    db.flush()
    return member_output(db, member)
