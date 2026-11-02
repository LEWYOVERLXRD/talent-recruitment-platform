"""求职者岗位浏览、简历和投递闭环。"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints import applications, auth, candidates, delivery, jobseeker, jobs, resumes, users
from app.models import Application, Candidate, CandidateSource, CompanyRole, JobAssignment, Recommendation, Resume, User, UserRole
from test_permissions import db as db_fixture


def client_for(db, uid):
    app = FastAPI()
    for router in [auth.router, jobs.router, candidates.router, resumes.router,
                   jobseeker.router, applications.router, delivery.router, users.router]:
        app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, uid)
    return TestClient(app)


def test_jobseeker_can_browse_manage_resume_and_apply(db_fixture, tmp_path, monkeypatch):
    from app.core import config
    monkeypatch.setattr(config.settings, "RESUME_STORAGE_DIR", Path(tmp_path), raising=False)
    db = db_fixture
    db.add(User(id=8, username="audit_other_jobseeker", password_hash="UNUSED_TEST_HASH",
                role=UserRole.jobseeker, enabled=True))
    db.add(User(id=15, username="audit_client_staff", password_hash="UNUSED_TEST_HASH",
                role=UserRole.recruiter, company_id=1, company_role=CompanyRole.staff, enabled=True))
    db.add(Candidate(id=23, name="AUDIT_OTHER_SEEKER", source=CandidateSource.self_apply,
                     candidate_user_id=8))
    db.flush()
    db.add(Resume(candidate_id=23, file_path="other/resume.txt", original_name="other.txt",
                  file_type="txt", version=1, uploaded_by=8, is_primary=True,
                  extraction_status="pending"))
    db.commit()
    foreign_resume_id = db.query(Resume.id).filter(Resume.candidate_id == 23).scalar()

    with client_for(db, 7) as seeker:
        jobs_response = seeker.get("/api/v1/jobs")
        assert jobs_response.status_code == 200
        assert jobs_response.json()["items"]
        assert all(item["status"] == "open" for item in jobs_response.json()["items"])
        assert all(item["source"] == "headhunter_created" for item in jobs_response.json()["items"])
        assert jobs_response.json()["items"][0]["contact_person"] is None

        profile = seeker.get("/api/v1/jobseeker/profile")
        assert profile.status_code == 200
        candidate_id = profile.json()["id"]

        updated = seeker.patch("/api/v1/jobseeker/profile", json={
            "name": "自助求职者", "current_position": "算法工程师", "education": "硕士",
        })
        assert updated.status_code == 200
        assert updated.json()["candidate_user_id"] == 7

        upload = seeker.post("/api/v1/jobseeker/resumes", files={"file": ("resume.txt", b"Python and machine learning")})
        assert upload.status_code == 200, upload.text
        resume_id = upload.json()["id"]
        assert seeker.get("/api/v1/jobseeker/resumes").json()["total"] == 1

        job_id = next(item["id"] for item in jobs_response.json()["items"] if item["client_company_id"] == 1)
        assignment_id = db.query(JobAssignment.id).filter_by(job_id=job_id, owner_user_id=2).scalar()
        assert seeker.post("/api/v1/applications", json={"job_id": job_id, "resume_id": foreign_resume_id, "assignment_id": assignment_id}).status_code == 404
        created = seeker.post("/api/v1/applications", json={"job_id": job_id, "resume_id": resume_id, "assignment_id": assignment_id})
        assert created.status_code == 201, created.text
        application_id = created.json()["id"]
        assert created.json()["status"] == "submitted"
        assert "rejection_reason_note" not in created.json()
        assert seeker.post("/api/v1/applications", json={"job_id": job_id, "resume_id": resume_id, "assignment_id": assignment_id}).status_code == 409

        mine = seeker.get("/api/v1/applications/me")
        assert mine.status_code == 200 and mine.json()[0]["id"] == application_id

    assignment_id = db.query(JobAssignment.id).filter_by(job_id=10, owner_user_id=2).first()[0]
    with client_for(db, 2) as publisher:
        internal = publisher.get("/api/v1/applications")
        assert internal.status_code == 200 and internal.json()[0]["id"] == application_id
        resume_download = publisher.get(f"/api/v1/applications/{application_id}/resume")
        assert resume_download.status_code == 200
        assert resume_download.content == b"Python and machine learning"
        assert resume_download.headers["cache-control"] == "private, no-store"
        rejected = publisher.patch(f"/api/v1/applications/{application_id}/status", json={
            "status": "rejected", "rejection_reason_category": "经验不匹配", "rejection_reason_note": "岗位经验要求与当前经历不匹配。",
        })
        assert rejected.status_code == 200, rejected.text
        assert publisher.get(f"/api/v1/applications/{application_id}/resume").status_code == 200
        assert publisher.patch(f"/api/v1/applications/{application_id}/status", json={"status": "screening"}).status_code == 409
        assert publisher.patch(f"/api/v1/applications/{application_id}/status", json={"status": "withdrawn"}).status_code == 422
        assert publisher.get("/api/v1/applications/99999/resume").status_code == 404
        reviewed = publisher.post(f"/api/v1/applications/{application_id}/review", json={
            "decision": "pending", "review_note": "继续沟通后决定是否推荐",
        })
        assert reviewed.status_code == 200, reviewed.text
        created_recommendation = publisher.post(
            f"/api/v1/applications/{application_id}/recommendation", json={"assignment_id": assignment_id}
        )
        assert created_recommendation.status_code == 201, created_recommendation.text
        assert created_recommendation.json()["application_id"] == application_id
        recommendation = db.query(Recommendation).filter_by(application_id=application_id).one()
        source_candidate = db.get(Candidate, candidate_id)
        working_candidate = db.get(Candidate, recommendation.candidate_id)
        assert source_candidate.provider_id is None and source_candidate.candidate_user_id == 7
        assert working_candidate.provider_id is not None and working_candidate.candidate_user_id is None

    with client_for(db, 15) as staff:
        assert staff.get("/api/v1/applications").status_code == 403
        assert staff.get(f"/api/v1/applications/{application_id}/resume").status_code == 403

    with client_for(db, 3) as other_hunter:
        assert other_hunter.get("/api/v1/applications").status_code == 200
        assert other_hunter.get("/api/v1/applications").json() == []
        assert other_hunter.get(f"/api/v1/applications/{application_id}/resume").status_code == 404

    with client_for(db, 1) as admin:
        assert admin.get(f"/api/v1/applications/{application_id}/resume").status_code == 200

    application = db.query(Application).filter_by(id=application_id).one()
    original_resume_id = application.resume_id
    application.resume_id = foreign_resume_id
    db.commit()
    with client_for(db, 4) as recruiter:
        assert recruiter.get("/api/v1/applications").status_code == 403
        assert recruiter.get(f"/api/v1/applications/{application_id}/resume").status_code == 403
    application.resume_id = original_resume_id
    db.commit()

    with client_for(db, 7) as seeker:
        mine = seeker.get("/api/v1/applications/me")
        assert mine.status_code == 200 and mine.json()[0]["status"] == "rejected"
        assert "rejection_reason_note" not in mine.json()[0]
        assert seeker.get(f"/api/v1/applications/{application_id}").status_code in (404, 405)
