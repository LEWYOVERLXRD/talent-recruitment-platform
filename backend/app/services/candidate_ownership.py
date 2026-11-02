"""建档和转派的归属校验，始终保留历史建档人。"""
from fastapi import HTTPException

from app.models import Candidate, ServiceProvider, UserRole
from app.services.agency_service import (
    active_member, lock_users, locked_agency, mutation, provider_for_user,
    require_enabled, require_hunter, require_manager,
)


def creation_identity(db, user, payload):
    require_enabled(user)
    if user.role not in (UserRole.headhunter, UserRole.admin):
        raise HTTPException(403, "当前角色无权创建候选人")
    if user.role == UserRole.admin:
        if payload.ownership != "individual" or payload.owner_user_id is None:
            raise HTTPException(422, "管理员建档需指定个人猎头负责人")
        owner = lock_users(db, [payload.owner_user_id]).get(payload.owner_user_id)
        require_hunter(owner)
        return provider_for_user(db, owner), owner.id
    if payload.owner_user_id not in (None, user.id):
        raise HTTPException(403, "不能替其他顾问指定建档归属")
    if payload.ownership == "individual":
        current = lock_users(db, [user.id])[user.id]
        require_hunter(current)
        return provider_for_user(db, current), current.id
    member = active_member(db, user.id)
    if member is None:
        raise HTTPException(403, "没有有效机构")
    agency = locked_agency(db, member.agency_id)
    current = lock_users(db, [user.id])[user.id]
    member = active_member(db, user.id, agency.id, lock=True)
    require_hunter(current)
    if agency.status != "active" or member is None:
        raise HTTPException(403, "机构或成员已失效")
    provider = db.query(ServiceProvider).filter(ServiceProvider.agency_id == agency.id).one()
    return provider, user.id


@mutation
def transfer_candidate(db, user, candidate_id, owner_user_id):
    require_enabled(user)
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(404, "候选人不存在")
    provider = db.get(ServiceProvider, candidate.provider_id) if candidate.provider_id else None
    if provider is None or provider.kind != "agency":
        raise HTTPException(409, "本期仅支持机构档案在同机构内转派")
    agency = locked_agency(db, provider.agency_id)
    require_manager(db, user, agency)
    target = lock_users(db, [user.id, owner_user_id]).get(owner_user_id)
    require_hunter(target)
    if active_member(db, owner_user_id, agency.id, lock=True) is None:
        raise HTTPException(409, "负责人必须是本机构有效成员")
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).populate_existing().with_for_update().one()
    if candidate.provider_id != provider.id:
        raise HTTPException(409, "归属已发生变化，请重试")
    candidate.owner_user_id = owner_user_id
    db.flush()
    return candidate


def lock_candidate_for_write(db, user, candidate_id):
    """按机构→用户→候选人加锁，并在锁后重新检查当前权限。"""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(404, "候选人不存在")
    provider = db.get(ServiceProvider, candidate.provider_id) if candidate.provider_id else None
    agency = locked_agency(db, provider.agency_id) if provider and provider.kind == "agency" else None
    current = lock_users(db, [user.id]).get(user.id)
    if current is None:
        raise HTTPException(403, "账号已失效")
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).populate_existing().with_for_update().one()
    allowed = current.enabled and current.role == UserRole.admin
    if current.enabled and current.role == UserRole.jobseeker:
        allowed = candidate.candidate_user_id == current.id
    if current.enabled and current.role == UserRole.headhunter and provider:
        if provider.kind == "individual":
            allowed = provider.user_id == current.id and candidate.owner_user_id == current.id
        elif agency.status == "active":
            member = active_member(db, current.id, agency.id, lock=True)
            allowed = member is not None and (member.role == "manager" or candidate.owner_user_id == current.id)
    if not allowed:
        raise HTTPException(403, "当前已无候选人访问权限")
    return candidate
