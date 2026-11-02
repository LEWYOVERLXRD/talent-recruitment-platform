"""按机构→用户→需求→承接加锁；初始定位后重新核验对象集合。"""
from fastapi import HTTPException

from app.models import Agency, AgencyMember, Job, JobAssignment, ServiceProvider, User


def lock_context(db, actor_id, job_id, *, provider_ids=(), user_ids=()):
    discovered = {row[0] for row in db.query(JobAssignment.provider_id).filter(
        JobAssignment.job_id == job_id).all()}
    providers = db.query(ServiceProvider).filter(
        ServiceProvider.id.in_(discovered | set(provider_ids))).populate_existing().all()
    agency_ids = {p.agency_id for p in providers if p.agency_id is not None}
    ids = {actor_id, *user_ids, *(p.user_id for p in providers if p.user_id is not None)}
    agency_ids.update(row[0] for row in db.query(AgencyMember.agency_id).filter(
        AgencyMember.user_id.in_(ids), AgencyMember.status == "active").all())
    agencies = db.query(Agency).filter(Agency.id.in_(agency_ids)).order_by(
        Agency.id).populate_existing().with_for_update().all() if agency_ids else []
    users = {u.id: u for u in db.query(User).filter(User.id.in_(ids)).order_by(
        User.id).populate_existing().with_for_update().all()}
    actor = users.get(actor_id)
    if actor is None or not actor.enabled:
        raise HTTPException(403, "账号已失效")
    # 使用当前读，避免 MySQL REPEATABLE READ 的旧快照继续授权。
    members = db.query(AgencyMember).filter(AgencyMember.user_id.in_(ids)).order_by(
        AgencyMember.id).populate_existing().with_for_update().all()
    member_agencies = {m.agency_id for m in members if m.status == "active"}
    if not member_agencies.issubset(agency_ids):
        raise HTTPException(409, "机构身份已变化，请刷新后重试")
    job = db.query(Job).filter(Job.id == job_id).populate_existing().with_for_update().first()
    if job is None:
        raise HTTPException(404, "招聘需求不存在或无权访问")
    assignments = db.query(JobAssignment).filter(JobAssignment.job_id == job_id).order_by(
        JobAssignment.id).populate_existing().with_for_update().all()
    if {a.provider_id for a in assignments} - discovered:
        raise HTTPException(409, "需求承接已变化，请刷新后重试")
    return actor, job, assignments, users, {agency.id: agency for agency in agencies}


def lock_match_context(db, actor_id, job_id, candidate_id):
    """LLM 返回后按机构→用户→需求→承接→候选人顺序锁定并复核。"""
    from app.models import Candidate

    candidate_probe = db.get(Candidate, candidate_id)
    if candidate_probe is None:
        raise HTTPException(404, "候选人不存在")
    candidate_provider = db.get(ServiceProvider, candidate_probe.provider_id) if candidate_probe.provider_id else None
    providers = db.query(ServiceProvider).join(JobAssignment,
        JobAssignment.provider_id == ServiceProvider.id).filter(JobAssignment.job_id == job_id).all()
    provider_ids = {p.id for p in providers}
    if candidate_provider:
        provider_ids.add(candidate_provider.id)
    providers = db.query(ServiceProvider).filter(ServiceProvider.id.in_(provider_ids)).populate_existing().all()
    agency_ids = {p.agency_id for p in providers if p.agency_id is not None}
    ids = {actor_id, *(p.user_id for p in providers if p.user_id is not None)}
    agency_ids.update(row[0] for row in db.query(AgencyMember.agency_id).filter(
        AgencyMember.user_id.in_(ids), AgencyMember.status == "active").all())
    agencies = db.query(Agency).filter(Agency.id.in_(agency_ids)).order_by(
        Agency.id).populate_existing().with_for_update().all() if agency_ids else []
    users = {u.id: u for u in db.query(User).filter(User.id.in_(ids)).order_by(
        User.id).populate_existing().with_for_update().all()}
    actor = users.get(actor_id)
    if actor is None or not actor.enabled:
        raise HTTPException(403, "账号已失效")
    memberships = db.query(AgencyMember).filter(AgencyMember.user_id.in_(ids)).order_by(
        AgencyMember.id).populate_existing().with_for_update().all()
    member_agencies = {m.agency_id for m in memberships if m.status == "active"}
    if not member_agencies.issubset(agency_ids):
        raise HTTPException(409, "机构身份已变化，请刷新后重试")
    job = db.query(Job).filter(Job.id == job_id).populate_existing().with_for_update().first()
    if job is None:
        raise HTTPException(404, "招聘需求不存在或无权访问")
    assignments = db.query(JobAssignment).filter(JobAssignment.job_id == job_id).order_by(
        JobAssignment.id).populate_existing().with_for_update().all()
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).populate_existing().with_for_update().first()
    if candidate is None or candidate.provider_id != (candidate_provider.id if candidate_provider else None):
        raise HTTPException(409, "候选人归属已发生变化，请重试")
    return (actor, job, candidate, assignments, users, memberships,
            {p.id: p for p in providers}, {agency.id: agency for agency in agencies})
