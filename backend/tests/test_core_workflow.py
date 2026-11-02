"""猎头主链跨模块 API 集成回归，不连接外部服务。"""
from datetime import datetime, timezone
import json
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.models import User
from app.services import match_service, skill_service
from test_job_assignments import assignment_db
from test_permissions import client_for, db
from match_fixtures import VALID_MATCH


@pytest.fixture
def private_files(tmp_path, monkeypatch):
    path = tmp_path / "private"
    monkeypatch.setattr(settings, "RESUME_STORAGE_DIR", path, raising=False)
    return path


def test_headhunter_workflow_from_authorized_job_to_customer_feedback(assignment_db, private_files):
    db = assignment_db
    db.get(User, 5).company_id = 1
    db.get(User, 5).company_role = "staff"
    db.commit()

    with client_for(db, 4) as customer:
        job = customer.post("/api/v1/jobs", json={
            "title": "资深算法工程师", "description": "负责模型研发与落地",
            "requirements": "熟悉 Python 和机器学习", "contact_person": "客户联系人",
            "contact_info": "客户联系方式",
        })
        assert job.status_code == 200, job.text
        job_id = job.json()["id"]
        assert customer.post(f"/api/v1/jobs/{job_id}/confirm", json={"expected_version": 1}).status_code == 200
        invitation = customer.post(f"/api/v1/jobs/{job_id}/invitations", json={
            "provider_kind": "agency", "target_id": 1, "expected_version": 1,
        })
        assert invitation.status_code == 200, invitation.text
        assignment_id = invitation.json()["id"]

    with client_for(db, 8) as manager:
        accepted = manager.post(f"/api/v1/assignments/{assignment_id}/accept", json={"expected_round": 1})
        assert accepted.status_code == 200, accepted.text
        transfer = manager.post(f"/api/v1/assignments/{assignment_id}/owner", json={
            "expected_round": 1, "expected_owner_user_id": 8, "owner_user_id": 10,
        })
        assert transfer.status_code == 200, transfer.text

    with client_for(db, 10) as consultant:
        candidate = consultant.post("/api/v1/candidates", json={
            "ownership": "agency", "name": "合成候选人", "current_position": "算法工程师",
            "years_of_experience": 6,
        })
        assert candidate.status_code == 200, candidate.text
        candidate_id = candidate.json()["id"]
        upload = consultant.post(
            f"/api/v1/candidates/{candidate_id}/resumes",
            files={"file": ("synthetic-resume.txt", "Python machine learning delivery experience".encode())},
        )
        assert upload.status_code == 200, upload.text
        resume_id = upload.json()["id"]
        parsed = consultant.post(f"/api/v1/resumes/{resume_id}/parse")
        assert parsed.status_code == 200 and parsed.json()["parse_status"] == "success"
        with patch.object(skill_service.llm, "chat", return_value=json.dumps({
            "skills": [{"name": "Python", "category": "language", "evidence": "Python"}],
        })):
            skills = consultant.post(f"/api/v1/resumes/{resume_id}/extract-skills", json={
                "expected_skill_revision": parsed.json()["skill_revision"],
            })
        assert skills.status_code == 200, skills.text
        skill_revision = skills.json()["skill_revision"]
        with patch.object(match_service.llm, "chat", return_value=VALID_MATCH):
            match = consultant.post("/api/v1/matches", json={
                "job_id": job_id, "candidate_id": candidate_id, "resume_id": resume_id,
                "expected_job_version": 1, "expected_skill_revision": skill_revision,
            })
        assert match.status_code == 200, match.text
        assert match.json()["input_snapshot"]["resume_id"] == resume_id

        communication = consultant.post(f"/api/v1/candidates/{candidate_id}/communications", json={
            "job_id": job_id, "comm_type": "wechat", "content": "候选人确认有意了解岗位",
            "result": "considering", "communicated_at": datetime.now(timezone.utc).isoformat(),
        })
        assert communication.status_code == 200, communication.text
        communication_id = communication.json()["id"]
        recommendation = consultant.post("/api/v1/recommendations", json={
            "assignment_id": assignment_id, "candidate_id": candidate_id,
        })
        assert recommendation.status_code == 201, recommendation.text
        recommendation_id = recommendation.json()["id"]
        prepared = consultant.patch(f"/api/v1/recommendations/{recommendation_id}", json={
            "expected_version": 1, "resume_id": resume_id, "communication_id": communication_id,
            "recommendation_note": "经验与岗位要求相关，建议安排技术面试。",
        })
        assert prepared.status_code == 200, prepared.text
        contacted = consultant.post(f"/api/v1/recommendations/{recommendation_id}/stage", json={
            "expected_version": prepared.json()["version"], "status": "contacted",
            "communication_id": communication_id,
        })
        assert contacted.status_code == 200, contacted.text
        ready = consultant.post(f"/api/v1/recommendations/{recommendation_id}/stage", json={
            "expected_version": contacted.json()["version"], "status": "pending_recommend",
            "communication_id": communication_id,
        })
        assert ready.status_code == 200, ready.text
        submitted = consultant.post(f"/api/v1/recommendations/{recommendation_id}/submit", json={
            "expected_version": ready.json()["version"],
            "share_basis": "候选人已明确同意将该版本简历提供给客户企业。",
            "share_confirmed_at": datetime.now(timezone.utc).isoformat(),
        })
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "recommended"
        assert submitted.json()["delivery_snapshot"]["candidate"]["name"] == "合成候选人"

    with client_for(db, 5) as customer_staff:
        detail = customer_staff.get(f"/api/v1/recommendations/{recommendation_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["delivery_snapshot"]["resume"]["parsed_text"]
        feedback = customer_staff.post(f"/api/v1/recommendations/{recommendation_id}/feedbacks", json={
            "expected_version": detail.json()["version"], "conclusion": "accepted",
            "feedback_type": "recommendation", "content": "资料符合岗位方向，进入面试流程。",
        })
        assert feedback.status_code == 200, feedback.text
        assert customer_staff.get(f"/api/v1/candidates/{candidate_id}/communications").status_code == 403
        history = customer_staff.get(f"/api/v1/recommendations/{recommendation_id}/feedbacks")
        assert history.status_code == 200 and history.json()["total"] == 1

