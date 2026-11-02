"""简历、私有附件及当前版本技能。"""
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models import User, UserRole
from app.schemas.resume import PrimaryChange, ResumeDetail, ResumePage, ResumeSummary, SkillCreate, SkillReview, SkillRevision, SkillsOut
from app.services import resume_files, resume_service, skill_service

router = APIRouter(tags=["简历与技能"])
actor = require_role(UserRole.admin, UserRole.headhunter, UserRole.jobseeker)


@router.post("/candidates/{candidate_id}/resumes", response_model=ResumeSummary, summary="上传新简历版本并设为主简历")
def upload(candidate_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(actor)):
    try:
        return resume_service.upload_resume(db, user, candidate_id, file)
    finally:
        file.file.close()


@router.get("/candidates/{candidate_id}/resumes", response_model=ResumePage, summary="简历版本分页")
def versions(candidate_id: int, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
             db: Session = Depends(get_db), user: User = Depends(actor)):
    return resume_service.list_resumes(db, user, candidate_id, page, size)


@router.get("/resumes/{resume_id}", response_model=ResumeDetail, summary="简历正文和解析状态")
def detail(resume_id: int, db: Session = Depends(get_db), user: User = Depends(actor)):
    return resume_service.get_resume(db, user, resume_id)


@router.get("/resumes/{resume_id}/download", summary="鉴权下载私有简历", response_class=FileResponse)
def download(resume_id: int, db: Session = Depends(get_db), user: User = Depends(actor)):
    row = resume_service.get_resume(db, user, resume_id)
    return FileResponse(resume_files.safe_path(row.file_path), filename=row.original_name or "resume",
                        media_type="application/octet-stream", headers={"Cache-Control": "private, no-store"})


@router.post("/resumes/{resume_id}/primary", response_model=ResumeSummary, summary="切换主简历")
def primary(resume_id: int, payload: PrimaryChange, db: Session = Depends(get_db), user: User = Depends(actor)):
    return resume_service.set_primary(db, user, resume_id, payload.expected_primary_id)


@router.post("/resumes/{resume_id}/parse", response_model=ResumeDetail, summary="本地解析正文，成功后冻结")
def parse(resume_id: int, db: Session = Depends(get_db), user: User = Depends(actor)):
    return resume_service.parse_resume(db, user, resume_id)


@router.post("/resumes/{resume_id}/extract-skills", response_model=SkillsOut, summary="AI抽取技能，保留人工核对结果")
def extract(resume_id: int, payload: SkillRevision, db: Session = Depends(get_db), user: User = Depends(actor)):
    return skill_service.extract_skills(db, user, resume_id, payload.expected_skill_revision)


@router.get("/resumes/{resume_id}/skills", response_model=SkillsOut, summary="当前简历技能与原文证据")
def skills(resume_id: int, db: Session = Depends(get_db), user: User = Depends(actor)):
    return skill_service.list_skills(db, user, resume_id)


@router.post("/resumes/{resume_id}/skills", response_model=SkillsOut, summary="人工新增带证据技能")
def add(resume_id: int, payload: SkillCreate, db: Session = Depends(get_db), user: User = Depends(actor)):
    return skill_service.add_skill(db, user, resume_id, payload)


@router.patch("/resumes/{resume_id}/skills/{relation_id}", response_model=SkillsOut, summary="人工核对技能")
def review(resume_id: int, relation_id: int, payload: SkillReview, db: Session = Depends(get_db), user: User = Depends(actor)):
    return skill_service.review_skill(db, user, resume_id, relation_id, payload)
