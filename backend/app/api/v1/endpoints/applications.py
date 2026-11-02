"""求职投递接口：求职者自助投递，企业招聘方处理状态。"""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models import Application, Candidate, Job, Resume, User, UserRole
from app.schemas.application import ApplicationCreate, ApplicationInternalOut, ApplicationMineOut, ApplicationReviewUpdate, ApplicationStatusUpdate
from app.services import jobseeker_service, resume_files

router = APIRouter(prefix="/applications", tags=["求职投递"])


def mine_out(db, row: Application) -> ApplicationMineOut:
    job = db.get(Job, row.job_id)
    resume = db.get(Resume, row.resume_id)
    kind = row.record_kind.value if hasattr(row.record_kind, "value") else row.record_kind
    return ApplicationMineOut(
        id=row.id, job_id=row.job_id, job_title=job.title if job else f"岗位 #{row.job_id}",
        client_company_name=job.client_company_name if job else None,
        resume_id=row.resume_id, resume_name=resume.original_name if resume else None,
        status=row.status.value if hasattr(row.status, "value") else row.status,
        source=row.source.value if hasattr(row.source, "value") else row.source,
        submitted_at=row.submitted_at, status_updated_at=row.status_updated_at, created_at=row.created_at,
        review_status=row.review_status.value if hasattr(row.review_status, "value") else row.review_status,
        assignment_id=row.assignment_id,
        record_kind=kind,
        visibility_message="该人选已入库" if kind == "duplicate" else None,
    )


def internal_out(db, row: Application) -> ApplicationInternalOut:
    base = mine_out(db, row)
    kind = row.record_kind.value if hasattr(row.record_kind, "value") else row.record_kind
    if kind == "duplicate":
        data = base.model_dump()
        data.update({
            "resume_id": None, "resume_name": None, "client_company_name": None,
            "candidate_id": None, "applicant_user_id": None,
            "candidate_name": "该人选已入库", "rejection_reason_category": None,
            "rejection_reason_note": None, "publisher_user_id": None,
            "review_note": None, "can_recommend": False, "working_candidate_id": None,
        })
        return ApplicationInternalOut(**data)
    candidate = db.get(Candidate, row.candidate_id)
    kind = row.record_kind.value if hasattr(row.record_kind, "value") else row.record_kind
    data = base.model_dump()
    data.update({
        "candidate_id": row.candidate_id, "applicant_user_id": row.applicant_user_id,
        "candidate_name": candidate.name if candidate else f"候选人 #{row.candidate_id}",
        "rejection_reason_category": row.rejection_reason_category,
        "rejection_reason_note": row.rejection_reason_note,
        "publisher_user_id": row.publisher_user_id, "review_note": row.review_note,
        "can_recommend": (row.review_status.value if hasattr(row.review_status, "value") else row.review_status) in ("pending", "not_recommended"),
        "working_candidate_id": row.working_candidate_id, "record_kind": kind,
        "visibility_message": None,
    })
    return ApplicationInternalOut(**data)


@router.post("", response_model=ApplicationMineOut, status_code=201, summary="求职者投递岗位")
def create(payload: ApplicationCreate, db: Session = Depends(get_db), user: User = Depends(require_role(UserRole.jobseeker))):
    return mine_out(db, jobseeker_service.create_application(db, user, job_id=payload.job_id,
                                                             resume_id=payload.resume_id,
                                                             assignment_id=payload.assignment_id))


@router.get("/me", response_model=list[ApplicationMineOut], summary="求职者查看我的投递")
def mine(db: Session = Depends(get_db), user: User = Depends(require_role(UserRole.jobseeker))):
    return [mine_out(db, row) for row in jobseeker_service.list_my_applications(db, user)]


@router.get("", response_model=list[ApplicationInternalOut], summary="猎头查看自己发布岗位收到的投递")
def internal_list(db: Session = Depends(get_db), user: User = Depends(require_role(UserRole.admin, UserRole.headhunter))):
    return [internal_out(db, row) for row in jobseeker_service.list_internal_applications(db, user)]


@router.get("/{application_id}/resume", summary="企业下载投递时提交的固定简历版本")
def download_application_resume(application_id: int, db: Session = Depends(get_db),
                                user: User = Depends(require_role(UserRole.admin, UserRole.headhunter))):
    row = jobseeker_service.get_application_resume(db, user, application_id)
    return FileResponse(resume_files.safe_path(row.file_path), filename=row.original_name or "resume",
                        media_type="application/octet-stream", headers={"Cache-Control": "private, no-store"})


@router.patch("/{application_id}/status", response_model=ApplicationInternalOut, summary="企业推进求职投递状态")
def update_status(application_id: int, payload: ApplicationStatusUpdate, db: Session = Depends(get_db),
                  user: User = Depends(require_role(UserRole.admin, UserRole.headhunter))):
    return internal_out(db, jobseeker_service.update_application_status(db, user, application_id, payload))


@router.post("/{application_id}/review", response_model=ApplicationInternalOut, summary="猎头审核求职投递")
def review(application_id: int, payload: ApplicationReviewUpdate, db: Session = Depends(get_db),
            user: User = Depends(require_role(UserRole.admin, UserRole.headhunter))):
    return internal_out(db, jobseeker_service.review_application(db, user, application_id, payload))
