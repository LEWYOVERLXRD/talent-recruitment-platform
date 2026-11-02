"""候选人私有沟通、推荐固定交付与企业反馈接口。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models import Application, User, UserRole
from app.schemas.delivery import (
    ApplicationRecommendationCreate, CommunicationCreate, CommunicationOut, CommunicationPage, RecommendationCreate,
    RecommendationFeedbackCreate, RecommendationFeedbackOut, RecommendationFeedbackPage,
    RecommendationPage, RecommendationRefresh, RecommendationStage, RecommendationSubmit,
    RecommendationUpdate,
)
from app.services import delivery_service

router = APIRouter(tags=["猎头沟通与推荐交付"])
_WORK_ROLES = (UserRole.headhunter, UserRole.admin)
_RECOMMENDATION_ROLES = (UserRole.headhunter, UserRole.recruiter, UserRole.admin)


@router.get("/candidates/{candidate_id}/communications", response_model=CommunicationPage)
def communications(candidate_id: int, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                   db: Session = Depends(get_db), user: User = Depends(require_role(*_WORK_ROLES))):
    return delivery_service.list_communications(db, user, candidate_id, page, size)


@router.post("/candidates/{candidate_id}/communications", response_model=CommunicationOut)
def add_communication(candidate_id: int, payload: CommunicationCreate, db: Session = Depends(get_db),
                       user: User = Depends(require_role(*_WORK_ROLES))):
    return delivery_service.add_communication(db, user, candidate_id, payload)


@router.get("/communications/{communication_id}", response_model=CommunicationOut)
def communication_detail(communication_id: int, db: Session = Depends(get_db),
                         user: User = Depends(require_role(*_WORK_ROLES))):
    return delivery_service.get_communication(db, user, communication_id)


@router.get("/recommendations", response_model=RecommendationPage)
def recommendations(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                    db: Session = Depends(get_db), user: User = Depends(require_role(*_RECOMMENDATION_ROLES))):
    return delivery_service.list_recommendations(db, user, page, size)


@router.post("/recommendations", status_code=201)
def create_recommendation(payload: RecommendationCreate, db: Session = Depends(get_db),
                          user: User = Depends(require_role(UserRole.headhunter))):
    return delivery_service.create_recommendation(db, user, payload.assignment_id, payload.candidate_id)


@router.post("/applications/{application_id}/recommendation", status_code=201,
             summary="从猎头收到的求职投递创建推荐草稿")
def create_recommendation_from_application(application_id: int, payload: ApplicationRecommendationCreate,
                                           db: Session = Depends(get_db),
                                           user: User = Depends(require_role(UserRole.headhunter))):
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(404, "投递记录不存在")
    return delivery_service.create_recommendation(
        db, user, payload.assignment_id, candidate_id=application.candidate_id,
        application_id=application_id,
    )


@router.get("/recommendations/{recommendation_id}")
def recommendation_detail(recommendation_id: int, db: Session = Depends(get_db),
                          user: User = Depends(require_role(*_RECOMMENDATION_ROLES))):
    return delivery_service.get_recommendation(db, user, recommendation_id)


@router.patch("/recommendations/{recommendation_id}")
def update_recommendation(recommendation_id: int, payload: RecommendationUpdate, db: Session = Depends(get_db),
                          user: User = Depends(require_role(UserRole.headhunter))):
    return delivery_service.update_recommendation(db, user, recommendation_id, payload)


@router.post("/recommendations/{recommendation_id}/stage")
def stage_recommendation(recommendation_id: int, payload: RecommendationStage, db: Session = Depends(get_db),
                         user: User = Depends(require_role(UserRole.headhunter))):
    return delivery_service.stage_recommendation(db, user, recommendation_id, payload)


@router.post("/recommendations/{recommendation_id}/refresh-context")
def refresh_context(recommendation_id: int, payload: RecommendationRefresh, db: Session = Depends(get_db),
                    user: User = Depends(require_role(UserRole.headhunter))):
    return delivery_service.refresh_recommendation_context(db, user, recommendation_id, payload)


@router.post("/recommendations/{recommendation_id}/submit")
def submit_recommendation(recommendation_id: int, payload: RecommendationSubmit, db: Session = Depends(get_db),
                          user: User = Depends(require_role(UserRole.headhunter))):
    return delivery_service.submit_recommendation(db, user, recommendation_id, payload)


@router.get("/recommendations/{recommendation_id}/resume/download")
def recommendation_resume(recommendation_id: int, db: Session = Depends(get_db),
                          user: User = Depends(require_role(*_RECOMMENDATION_ROLES))):
    resume, path = delivery_service.download_recommendation_resume(db, user, recommendation_id)
    return FileResponse(path, filename=resume.original_name or "resume",
                        media_type="application/octet-stream", headers={"Cache-Control": "private, no-store"})


@router.get("/recommendations/{recommendation_id}/feedbacks", response_model=RecommendationFeedbackPage)
def feedbacks(recommendation_id: int, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
              db: Session = Depends(get_db), user: User = Depends(require_role(*_RECOMMENDATION_ROLES))):
    return delivery_service.list_feedbacks(db, user, recommendation_id, page, size)


@router.post("/recommendations/{recommendation_id}/feedbacks", response_model=RecommendationFeedbackOut)
def add_feedback(recommendation_id: int, payload: RecommendationFeedbackCreate, db: Session = Depends(get_db),
                 user: User = Depends(require_role(UserRole.recruiter))):
    return delivery_service.add_feedback(db, user, recommendation_id, payload)
