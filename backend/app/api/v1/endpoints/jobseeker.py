"""求职者自助档案和简历接口。"""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models import User, UserRole
from app.schemas.candidate import CandidateOut, CandidateUpdate
from app.schemas.resume import PrimaryChange, ResumePage, ResumeSummary
from app.services import jobseeker_service, resume_files, resume_service

router = APIRouter(prefix="/jobseeker", tags=["求职者"])


@router.get("/profile", response_model=CandidateOut, summary="获取求职者个人档案")
def profile(db: Session = Depends(get_db), user: User = Depends(require_role(UserRole.jobseeker))):
    return jobseeker_service.get_or_create_profile(db, user)


@router.patch("/profile", response_model=CandidateOut, summary="维护求职者个人档案")
def update_profile(payload: CandidateUpdate, db: Session = Depends(get_db), user: User = Depends(require_role(UserRole.jobseeker))):
    return jobseeker_service.update_profile(db, user, payload)


@router.get("/resumes", response_model=ResumePage, summary="查看我的简历")
def resumes(db: Session = Depends(get_db), user: User = Depends(require_role(UserRole.jobseeker))):
    row = jobseeker_service.get_or_create_profile(db, user)
    return resume_service.list_resumes(db, user, row.id, page=1, size=100)


@router.post("/resumes", response_model=ResumeSummary, summary="上传我的简历")
def upload(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_role(UserRole.jobseeker))):
    row = jobseeker_service.get_or_create_profile(db, user)
    try:
        return resume_service.upload_resume(db, user, row.id, file)
    finally:
        file.file.close()


@router.post("/resumes/{resume_id}/primary", response_model=ResumeSummary, summary="设置我的主简历")
def primary(resume_id: int, payload: PrimaryChange, db: Session = Depends(get_db), user: User = Depends(require_role(UserRole.jobseeker))):
    return resume_service.set_primary(db, user, resume_id, payload.expected_primary_id)


@router.post("/resumes/{resume_id}/parse", summary="解析我的简历")
def parse(resume_id: int, db: Session = Depends(get_db), user: User = Depends(require_role(UserRole.jobseeker))):
    return resume_service.parse_resume(db, user, resume_id)
