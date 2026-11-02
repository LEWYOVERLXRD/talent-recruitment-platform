"""D 批沟通、固定推荐交付与客户追加反馈集成测试。"""
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.models import Agency, AgencyMember, Candidate, Job, JobAssignment, Recommendation, RecommendationFeedback, Resume, ServiceProvider, User
from app.services import assignment_service, delivery_service, job_service
from app.schemas.delivery import CommunicationCreate, RecommendationFeedbackCreate, RecommendationStage, RecommendationSubmit, RecommendationUpdate
from app.schemas.job import JobCreate
from app.services import resume_files, resume_service
from test_job_assignments import assignment_db, create_confirmed_job, invite
from test_permissions import client_for, db


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RESUME_STORAGE_DIR", tmp_path / "private", raising=False)
    return tmp_path / "private"


def active_task(db):
    job = create_confirmed_job(db)
    row = invite(db, 4, job.id, 1)
    assignment_service.decide_invitation(db, db.get(User, 8), row.id, expected_round=1, accept=True)
    return job, db.query(JobAssignment).filter_by(id=row.id).one()


def add_candidate(db):
    candidate = db.get(Candidate, 20)
    candidate.provider_id = 20
    candidate.owner_user_id = 8
    db.commit()
    return candidate


def make_delivery(db, files):
    job, assignment = active_task(db)
    candidate = add_candidate(db)
    from app.models import Communication
    comm = Communication(candidate_id=candidate.id, job_id=job.id, comm_type="wechat", content="Candidate is interested",
                         result="considering", communicated_at=datetime(2026, 10, 22), created_by=8)
    db.add(comm)
    db.commit()
    path = files / "candidate.txt"
    files.mkdir(parents=True, exist_ok=True)
    path.write_text("Python, recommendation delivery experience", encoding="utf-8")
    import hashlib
    resume = Resume(candidate_id=candidate.id, file_path=path.name, original_name="candidate.txt", file_type="txt",
                    parsed_text="Python, recommendation delivery experience", parse_status="success", is_primary=True,
                    version=1, file_size=path.stat().st_size, file_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    db.add(resume)
    db.commit()
    draft = delivery_service.create_recommendation(db, db.get(User, 8), assignment.id, candidate.id)
    draft_id = draft["id"]
    updated = delivery_service.update_recommendation(db, db.get(User, 8), draft_id,
        RecommendationUpdate(expected_version=1, resume_id=resume.id, communication_id=comm.id,
                             recommendation_note="Strong fit based on relevant work and verified experience."))
    staged = delivery_service.stage_recommendation(db, db.get(User, 8), draft_id,
        RecommendationStage(expected_version=updated["version"], status="pending_recommend", communication_id=comm.id))
    submitted = delivery_service.submit_recommendation(db, db.get(User, 8), draft_id,
        RecommendationSubmit(expected_version=staged["version"], share_basis="Candidate explicitly confirmed sharing this resume with the client.",
                             share_confirmed_at=datetime.now(timezone.utc)))
    return job, assignment, candidate, comm, resume, submitted


def test_recommendation_delivery_and_both_customer_roles_can_feedback(assignment_db, files):
    db = assignment_db
    db.get(User, 5).company_id = 1
    db.commit()
    job, assignment, candidate, comm, resume, submitted = make_delivery(db, files)
    assert submitted["status"] == "recommended"
    assert submitted["delivery_snapshot"]["resume"]["parsed_text"].startswith("Python")

    with client_for(db, 4) as manager, client_for(db, 5) as staff:
        manager_feedback = manager.post(f"/api/v1/recommendations/{submitted['id']}/feedbacks", json={
            "expected_version": submitted["version"], "conclusion": "accepted", "feedback_type": "recommendation",
            "content": "The profile is relevant; proceed to interview.",
        })
        assert manager_feedback.status_code == 200, manager_feedback.text
        staff_feedback = staff.post(f"/api/v1/recommendations/{submitted['id']}/feedbacks", json={
            "expected_version": manager_feedback.json()["recommendation_version"],
            "conclusion": "interviewing", "feedback_type": "interview", "content": "Interview scheduled by our team.",
        })
        assert staff_feedback.status_code == 200, staff_feedback.text
        feedbacks = staff.get(f"/api/v1/recommendations/{submitted['id']}/feedbacks")
        assert feedbacks.status_code == 200 and feedbacks.json()["total"] == 2
        assert staff.get(f"/api/v1/recommendations/{submitted['id']}").json()["delivery_snapshot"]

    with client_for(db, 5) as staff:
        assert staff.post("/api/v1/assignments/1/cancel", json={"expected_round": 1, "reason": "not manager"}).status_code in (403, 404)
    assert db.query(RecommendationFeedback).filter_by(recommendation_id=submitted["id"]).count() == 2
    assert db.query(Recommendation).filter_by(id=submitted["id"]).one().status == "interviewing"


@pytest.mark.parametrize("conclusion,expected_status", [("passed", "passed"), ("rejected", "rejected")])
def test_interview_feedback_reaches_terminal_status_and_preserves_history(assignment_db, files, conclusion, expected_status):
    db = assignment_db
    db.get(User, 5).company_id = 1
    _, _, _, _, _, submitted = make_delivery(db, files)
    with client_for(db, 4) as customer:
        accepted = customer.post(f"/api/v1/recommendations/{submitted['id']}/feedbacks", json={
            "expected_version": submitted["version"], "conclusion": "accepted",
            "feedback_type": "recommendation", "content": "进入面试流程。",
        })
        assert accepted.status_code == 200, accepted.text
        interviewing = customer.post(f"/api/v1/recommendations/{submitted['id']}/feedbacks", json={
            "expected_version": accepted.json()["recommendation_version"], "conclusion": "interviewing",
            "feedback_type": "interview", "content": "已安排面试。",
        })
        assert interviewing.status_code == 200, interviewing.text
        content = "面试通过，建议进入后续招聘流程。" if conclusion == "passed" else "面试未通过，岗位要求与候选人当前情况不匹配。"
        terminal = customer.post(f"/api/v1/recommendations/{submitted['id']}/feedbacks", json={
            "expected_version": interviewing.json()["recommendation_version"], "conclusion": conclusion,
            "feedback_type": "interview", "content": content,
        })
        assert terminal.status_code == 200, terminal.text
        assert terminal.json()["to_status"] == expected_status
        detail = customer.get(f"/api/v1/recommendations/{submitted['id']}")
        assert detail.status_code == 200 and detail.json()["status"] == expected_status
        history = customer.get(f"/api/v1/recommendations/{submitted['id']}/feedbacks")
        assert history.status_code == 200 and history.json()["total"] == 3
        blocked = customer.post(f"/api/v1/recommendations/{submitted['id']}/feedbacks", json={
            "expected_version": terminal.json()["recommendation_version"], "conclusion": "interviewing",
            "feedback_type": "interview", "content": "不应从终态回到面试中。",
        })
        assert blocked.status_code == 409


@pytest.mark.parametrize("conclusion,expected_status", [("passed", "passed"), ("rejected", "rejected")])
def test_interview_feedback_reaches_terminal_status_and_preserves_history(assignment_db, files, conclusion, expected_status):
    db = assignment_db
    db.get(User, 5).company_id = 1
    _, _, _, _, _, submitted = make_delivery(db, files)
    with client_for(db, 4) as customer:
        accepted = customer.post(f"/api/v1/recommendations/{submitted['id']}/feedbacks", json={
            "expected_version": submitted["version"], "conclusion": "accepted",
            "feedback_type": "recommendation", "content": "进入面试流程。",
        })
        assert accepted.status_code == 200, accepted.text
        interviewing = customer.post(f"/api/v1/recommendations/{submitted['id']}/feedbacks", json={
            "expected_version": accepted.json()["recommendation_version"], "conclusion": "interviewing",
            "feedback_type": "interview", "content": "已安排面试。",
        })
        assert interviewing.status_code == 200, interviewing.text
        content = "面试通过，建议进入后续招聘流程。" if conclusion == "passed" else "面试未通过，岗位要求与候选人当前情况不匹配。"
        terminal = customer.post(f"/api/v1/recommendations/{submitted['id']}/feedbacks", json={
            "expected_version": interviewing.json()["recommendation_version"], "conclusion": conclusion,
            "feedback_type": "interview", "content": content,
        })
        assert terminal.status_code == 200, terminal.text
        assert terminal.json()["to_status"] == expected_status
        detail = customer.get(f"/api/v1/recommendations/{submitted['id']}")
        assert detail.status_code == 200 and detail.json()["status"] == expected_status
        history = customer.get(f"/api/v1/recommendations/{submitted['id']}/feedbacks")
        assert history.status_code == 200 and history.json()["total"] == 3
        blocked = customer.post(f"/api/v1/recommendations/{submitted['id']}/feedbacks", json={
            "expected_version": terminal.json()["recommendation_version"], "conclusion": "interviewing",
            "feedback_type": "interview", "content": "不应从终态回到面试中。",
        })
        assert blocked.status_code == 409


def test_customer_cannot_read_private_communication_or_draft(assignment_db, files):
    db = assignment_db
    job, assignment, candidate, comm, resume, submitted = make_delivery(db, files)
    row = db.query(Recommendation).filter_by(id=submitted["id"]).one()
    row.delivery_snapshot = None
    db.commit()
    with client_for(db, 4) as customer:
        assert customer.get(f"/api/v1/candidates/{candidate.id}/communications").status_code == 403
        assert customer.get(f"/api/v1/recommendations/{row.id}").status_code == 404


def test_other_customer_cannot_view_delivery_or_feedback(assignment_db, files):
    db = assignment_db
    job, assignment, candidate, comm, resume, submitted = make_delivery(db, files)
    with client_for(db, 5) as other_customer:
        assert other_customer.get(f"/api/v1/recommendations/{submitted['id']}").status_code == 404
        assert other_customer.post(f"/api/v1/recommendations/{submitted['id']}/feedbacks", json={
            "expected_version": submitted["version"], "conclusion": "accepted", "feedback_type": "recommendation",
            "content": "Not our company record.",
        }).status_code == 404


def test_old_assignment_round_cannot_refresh_into_new_round(assignment_db):
    db = assignment_db
    job, assignment = active_task(db)
    candidate = add_candidate(db)
    row = Recommendation(job_id=job.id, candidate_id=candidate.id, assignment_id=assignment.id,
                         assignment_round=assignment.round_no, created_by=8, job_version=job.version,
                         status="pending_contact", version=1)
    db.add(row)
    db.commit()
    assignment.status = "completed"
    assignment.ended_by, assignment.ended_at = 4, datetime(2026, 10, 22)
    db.commit()
    try:
        delivery_service.refresh_recommendation_context(db, db.get(User, 8), row.id,
            __import__('app.schemas.delivery', fromlist=['RecommendationRefresh']).RecommendationRefresh(
                expected_version=1, job_version=job.version, assignment_round=assignment.round_no))
    except HTTPException as error:
        assert error.status_code == 403
    else:
        pytest.fail("ended assignment must not reactivate an old recommendation draft")


def test_explicit_null_clears_preparation_communication(assignment_db, files):
    db = assignment_db
    job, assignment = active_task(db)
    candidate = add_candidate(db)
    from app.models import Communication
    comm = Communication(candidate_id=candidate.id, job_id=job.id, comm_type="wechat", content="Checked in",
                         result="considering", communicated_at=datetime(2026, 10, 22), created_by=8)
    db.add(comm)
    db.commit()
    draft = delivery_service.create_recommendation(db, db.get(User, 8), assignment.id, candidate.id)
    selected = delivery_service.update_recommendation(db, db.get(User, 8), draft["id"],
        RecommendationUpdate(expected_version=1, communication_id=comm.id))
    cleared = delivery_service.update_recommendation(db, db.get(User, 8), draft["id"],
        RecommendationUpdate(expected_version=selected["version"], communication_id=None))
    assert cleared["preparation_communication_id"] is None


def test_individual_delivery_history_survives_joining_an_agency(assignment_db, files):
    db = assignment_db
    job = create_confirmed_job(db)
    assignment = assignment_service.invite_provider(db, db.get(User, 4), job.id, "individual", 14, 1)
    assignment_service.decide_invitation(db, db.get(User, 14), assignment.id,
                                         expected_round=1, accept=True)
    provider = db.query(ServiceProvider).filter_by(kind="individual", user_id=14).one()
    candidate = Candidate(name="PERSONAL_HISTORY", created_by=14, provider_id=provider.id, owner_user_id=14)
    db.add(candidate)
    db.commit()
    from app.models import Communication
    comm = Communication(candidate_id=candidate.id, job_id=job.id, comm_type="wechat", content="Interested",
                         result="considering", communicated_at=datetime(2026, 10, 22), created_by=14)
    db.add(comm)
    path = files / "personal.txt"
    files.mkdir(parents=True, exist_ok=True)
    path.write_text("Personal resume", encoding="utf-8")
    import hashlib
    resume = Resume(candidate_id=candidate.id, file_path=path.name, original_name="personal.txt", file_type="txt",
                    parsed_text="Personal resume", parse_status="success", is_primary=True, version=1,
                    file_size=path.stat().st_size, file_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    db.add(resume)
    db.commit()
    draft = delivery_service.create_recommendation(db, db.get(User, 14), assignment.id, candidate.id)
    updated = delivery_service.update_recommendation(db, db.get(User, 14), draft["id"],
        RecommendationUpdate(expected_version=1, resume_id=resume.id, communication_id=comm.id,
                             recommendation_note="Relevant experience and clear technical fit."))
    staged = delivery_service.stage_recommendation(db, db.get(User, 14), draft["id"],
        RecommendationStage(expected_version=updated["version"], status="pending_recommend", communication_id=comm.id))
    submitted = delivery_service.submit_recommendation(db, db.get(User, 14), draft["id"],
        RecommendationSubmit(expected_version=staged["version"], share_basis="Candidate confirmed sharing.",
                             share_confirmed_at=datetime.now(timezone.utc)))

    db.add(Agency(id=3, name="AGENCY_JOINED_LATER", status="active", created_by=1))
    db.flush()
    db.add(ServiceProvider(kind="agency", agency_id=3))
    db.add(AgencyMember(agency_id=3, user_id=14, role="staff", status="active", invited_by=1))
    db.commit()
    with client_for(db, 14) as individual_owner:
        response = individual_owner.get("/api/v1/recommendations")
        detail = individual_owner.get(f"/api/v1/recommendations/{submitted['id']}")
    with client_for(db, 10) as unrelated_agency_manager:
        other = unrelated_agency_manager.get("/api/v1/recommendations")
    assert response.status_code == 200 and submitted["id"] in {r["id"] for r in response.json()["items"]}
    assert detail.status_code == 200 and detail.json()["delivery_snapshot"]
    assert other.status_code == 200 and submitted["id"] not in {r["id"] for r in other.json()["items"]}
