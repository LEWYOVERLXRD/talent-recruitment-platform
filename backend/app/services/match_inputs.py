"""匹配的实际输入快照及外部调用前后的一致性判断。"""
from fastapi import HTTPException

from app.models import JobAssignment, ParseStatus
from app.services.skill_service import skill_snapshot

JOB_FIELDS = ("title", "department", "description", "requirements", "location", "salary_min", "salary_max", "hiring_count")
CANDIDATE_FIELDS = ("current_company", "current_position", "years_of_experience", "education", "expected_salary", "expected_location")


def fields(obj, names):
    return {name: getattr(obj, name, None) for name in names}


def capture(db, job, candidate, resume, *, current=False):
    if resume is None or resume.candidate_id != candidate.id:
        raise HTTPException(422, "请选择属于该候选人的简历版本")
    if resume.parse_status != ParseStatus.success or not resume.parsed_text:
        raise HTTPException(409, "简历正文尚未成功解析")
    tasks = db.query(JobAssignment).filter_by(job_id=job.id, provider_id=candidate.provider_id,
                                            status="active", job_version=job.version)
    task = tasks.populate_existing().with_for_update().first() if current else tasks.first()
    if task is None:
        raise HTTPException(409, "当前无有效需求承接")
    return dict(
        schema_version=1, prompt_version="match-v2", job_id=job.id, job_version=job.version,
        candidate_id=candidate.id, provider_id=candidate.provider_id, candidate_owner_user_id=candidate.owner_user_id,
        assignment_id=task.id, assignment_round=task.round_no, assignment_owner_user_id=task.owner_user_id,
        job=fields(job, JOB_FIELDS), candidate=fields(candidate, CANDIDATE_FIELDS),
        resume_id=resume.id, resume_version=resume.version, file_sha256=resume.file_sha256,
        resume_text=resume.parsed_text, skill_revision=resume.skill_revision,
        skills=skill_snapshot(db, resume.id, current=current),
    )
