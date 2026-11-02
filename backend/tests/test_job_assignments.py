"""B 批定向承接 API 的隔离集成测试。"""
import pytest

from app.models import Agency, AgencyMember, Job, JobAssignment, ServiceProvider, User, UserRole
from app.schemas.job import JobCreate, JobUpdate
from app.services import assignment_service, job_service
from test_permissions import client_for, db


@pytest.fixture
def assignment_db(db):
    db.get(User, 4).real_name = "CLIENT_MANAGER"
    db.get(User, 5).company_role = "staff"
    db.add_all([
        User(id=8, username="AGENCY_MANAGER_A", password_hash="UNUSED_TEST_HASH", role=UserRole.headhunter, enabled=True),
        User(id=9, username="AGENCY_MANAGER_B", password_hash="UNUSED_TEST_HASH", role=UserRole.headhunter, enabled=True),
        User(id=10, username="AGENCY_STAFF_A", password_hash="UNUSED_TEST_HASH", role=UserRole.headhunter, enabled=True),
    ])
    db.flush()
    db.add_all([
        Agency(id=1, name="AGENCY_A", status="active", created_by=1),
        Agency(id=2, name="AGENCY_B", status="active", created_by=1),
        ServiceProvider(id=20, kind="agency", agency_id=1),
        ServiceProvider(id=21, kind="agency", agency_id=2),
        AgencyMember(id=20, agency_id=1, user_id=8, role="manager", status="active", invited_by=1),
        AgencyMember(id=21, agency_id=1, user_id=10, role="staff", status="active", invited_by=8),
        AgencyMember(id=22, agency_id=2, user_id=9, role="manager", status="active", invited_by=1),
    ])
    db.commit()
    return db


def create_confirmed_job(db):
    job = job_service.new_job(db, current_user=db.get(User, 4), payload=JobCreate(
        title="AI 算法工程师", description="负责模型训练和部署", requirements="5 年经验，熟悉 PyTorch",
        client_company_id=None, contact_person="CLIENT_CONTACT", contact_info="CLIENT_PRIVATE_CONTACT",
    ))
    job = job_service.confirm_job(db, current_user=db.get(User, 4), job_id=job.id, expected_version=1)
    return job


def invite(db, user_id, job_id, provider_id, version=1):
    return assignment_service.invite_provider(db, db.get(User, user_id), job_id,
                                              "agency", provider_id, version)


def test_two_agencies_can_be_independently_invited_and_accept(assignment_db):
    db = assignment_db
    job = create_confirmed_job(db)
    first = invite(db, 4, job.id, 1)
    second = invite(db, 4, job.id, 2)
    assert first.contact_info == "CLIENT_PRIVATE_CONTACT"  # customer sees own contact
    assert first.status == second.status == "invited"

    with client_for(db, 8) as agency_a, client_for(db, 9) as agency_b:
        assert agency_a.get(f"/api/v1/jobs/{job.id}").json()["contact_info"] is None
        assert agency_b.get(f"/api/v1/jobs/{job.id}").json()["contact_info"] is None
        assert agency_a.post(f"/api/v1/assignments/{first.id}/accept", json={"expected_round": 1}).status_code == 200
        assert agency_b.post(f"/api/v1/assignments/{second.id}/accept", json={"expected_round": 1}).status_code == 200
        assert agency_a.get("/api/v1/assignments").json()[0]["job_id"] == job.id
        assert agency_b.get("/api/v1/assignments").json()[0]["job_id"] == job.id
        assert agency_a.get(f"/api/v1/assignments/{second.id}").status_code == 404
        detail = agency_a.get(f"/api/v1/jobs/{job.id}").json()
        assert detail["contact_info"] == "CLIENT_PRIVATE_CONTACT"
    assert db.query(JobAssignment).filter_by(job_id=job.id, status="active").count() == 2


def test_assignment_subject_names_follow_visible_records_only(assignment_db):
    db = assignment_db
    job = create_confirmed_job(db)
    agency = invite(db, 4, job.id, 1)
    invite(db, 4, job.id, 2)
    individual = assignment_service.invite_provider(db, db.get(User, 4), job.id, "individual", 14, 1)
    with client_for(db, 4) as customer:
        records = customer.get("/api/v1/assignments").json()
        selected = {row["provider_name"] for row in records if row["job_id"] == job.id}
        assert selected == {"AGENCY_A", "AGENCY_B", "audit_user_14"}
    with client_for(db, 8) as manager:
        records = manager.get("/api/v1/assignments").json()
        assert len(records) == 1 and records[0]["provider_name"] == "AGENCY_A"
        detail = manager.get(f"/api/v1/assignments/{agency.id}").json()
        assert detail["provider_kind"] == "agency" and detail["contact_info"] is None
        assert "AGENCY_B" not in str(records)
    with client_for(db, 14) as hunter:
        detail = hunter.get(f"/api/v1/assignments/{individual.id}").json()
        assert detail["provider_kind"] == "individual"
        assert detail["provider_name"] == "audit_user_14"


def test_agency_owner_transfer_and_candidate_task_are_separate(assignment_db):
    db = assignment_db
    job = create_confirmed_job(db)
    assignment = invite(db, 4, job.id, 1)
    with client_for(db, 10) as staff, client_for(db, 8) as manager:
        assert staff.post(f"/api/v1/assignments/{assignment.id}/accept", json={"expected_round": 1}).status_code == 403
        assert manager.post(f"/api/v1/assignments/{assignment.id}/accept", json={"expected_round": 1}).status_code == 200
        assert manager.post(f"/api/v1/assignments/{assignment.id}/owner", json={
            "expected_round": 1, "expected_owner_user_id": 8, "owner_user_id": 10,
        }).status_code == 200
        assert staff.get("/api/v1/assignments").json()[0]["owner_user_id"] == 10
        assert manager.post(f"/api/v1/assignments/{assignment.id}/owner", json={
            "expected_round": 1, "expected_owner_user_id": 8, "owner_user_id": 10,
        }).status_code == 409


def test_job_terms_change_invalidates_acceptance_and_reinvite_is_a_new_round(assignment_db):
    db = assignment_db
    job = create_confirmed_job(db)
    assignment = invite(db, 4, job.id, 1)
    job = job_service.patch_job(db, current_user=db.get(User, 4), job_id=job.id,
                                payload=JobUpdate(expected_version=1, title="Principal AI Engineer"))
    assert job.version == 2 and job.confirmed_at is None
    with client_for(db, 8) as client:
        response = client.post(f"/api/v1/assignments/{assignment.id}/accept", json={"expected_round": 1})
        assert response.status_code == 409
    job_service.confirm_job(db, current_user=db.get(User, 4), job_id=job.id, expected_version=2)
    renewed = invite(db, 4, job.id, 1, version=2)
    assert renewed.id == assignment.id and renewed.round_no == 2
    assert assignment_service.list_assignment_events(db, db.get(User, 4), assignment.id)[-1].payload["round"] == 2


def test_close_cancels_assignment_without_changing_recommendation(assignment_db):
    db = assignment_db
    job = create_confirmed_job(db)
    first = invite(db, 4, job.id, 1)
    assignment_service.decide_invitation(db, db.get(User, 8), first.id,
                                         expected_round=1, accept=True)
    job_service.change_job_status(db, current_user=db.get(User, 4), job_id=job.id,
                                  expected_version=1, target_status=__import__("app.models", fromlist=["JobStatus"]).JobStatus.closed,
                                  reason="客户取消招聘计划")
    db.refresh(db.get(JobAssignment, first.id))
    assert db.get(JobAssignment, first.id).status == "cancelled"


def test_individual_invite_does_not_make_member_personal_provider(assignment_db):
    db = assignment_db
    job = create_confirmed_job(db)
    with pytest.raises(Exception):
        assignment_service.invite_provider(db, db.get(User, 8), job.id, "individual", 8, 1)
    db.rollback()
    assert db.query(ServiceProvider).filter_by(kind="individual", user_id=8).count() == 0


def test_hunter_cannot_create_customer_by_name(assignment_db):
    db = assignment_db
    from app.schemas.job import JobCreate
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        job_service.new_job(db, current_user=db.get(User, 2), payload=JobCreate(title="Role"))
    assert error.value.status_code == 422


from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import event
from app.models import AssignmentEvent, Candidate, JobProfile, JobStatus, MatchAnalysis
from app.schemas.agency import MemberLeave
from match_fixtures import match_payload, VALID_MATCH
from app.services import agency_service, match_service


def active_agency_task(db, owner=10):
    job = create_confirmed_job(db)
    task = invite(db, 4, job.id, 1)
    assignment_service.decide_invitation(db, db.get(User, 8), task.id, expected_round=1, accept=True)
    if owner != 8:
        assignment_service.transfer_owner(db, db.get(User, 8), task.id, expected_round=1,
                                          expected_owner_user_id=8, owner_user_id=owner)
    candidate = Candidate(name="AGENCY_ASSET", created_by=10, provider_id=20, owner_user_id=owner)
    db.add(candidate)
    db.commit()
    return job, task.id, candidate.id


def test_individual_invitation_and_safe_history(assignment_db):
    db = assignment_db
    job = create_confirmed_job(db)
    task = assignment_service.invite_provider(db, db.get(User, 4), job.id, "individual", 14, 1)
    with client_for(db, 14) as hunter:
        detail = hunter.get(f"/api/v1/assignments/{task.id}")
        assert detail.status_code == 200 and detail.json()["contact_info"] is None
        assert hunter.get(f"/api/v1/jobs/{job.id}/profile").status_code == 404
        assert hunter.post(f"/api/v1/assignments/{task.id}/accept", json={"expected_round":1}).status_code == 200
        assert hunter.get(f"/api/v1/jobs/{job.id}/profile").status_code == 200
    assignment_service.end_assignment(db, db.get(User,4), task.id,
                                      expected_round=1, complete=False, reason="客户撤权")
    with client_for(db,14) as hunter:
        assert hunter.get(f"/api/v1/jobs/{job.id}").status_code == 404
        assert hunter.get(f"/api/v1/jobs/{job.id}/profile").status_code == 404
        history = hunter.get(f"/api/v1/assignments/{task.id}")
        assert history.status_code == 200 and history.json()["contact_info"] is None
        events = hunter.get(f"/api/v1/assignments/{task.id}/events")
        assert events.status_code == 200 and "CLIENT_PRIVATE_CONTACT" not in events.text


@pytest.mark.parametrize("uid", [1,5,8,10,14])
def test_only_customer_manager_can_invite(assignment_db, uid):
    db = assignment_db
    job = create_confirmed_job(db)
    with client_for(db,uid) as client:
        assert client.post(f"/api/v1/jobs/{job.id}/invitations", json={
            "provider_kind":"agency","target_id":1,"expected_version":1}).status_code == 403
    assert db.query(JobAssignment).filter_by(job_id=job.id).count() == 0


def test_customer_options_and_provider_options_are_minimal(assignment_db):
    db = assignment_db
    with client_for(db,2) as hunter, client_for(db,4) as manager, client_for(db,5) as staff:
        options = hunter.get("/api/v1/companies/options")
        assert options.status_code == 200 and all(set(row)=={"id","name"} for row in options.json())
        providers = manager.get("/api/v1/service-providers")
        assert providers.status_code == 200
        assert all(set(row)=={"kind","target_id","display_name"} for row in providers.json())
        assert not any(row["kind"]=="individual" and row["target_id"]==8 for row in providers.json())
        assert staff.get("/api/v1/service-providers").status_code == 403


def test_old_invitation_can_be_declined_but_not_accepted(assignment_db):
    db = assignment_db
    job = create_confirmed_job(db)
    task = invite(db,4,job.id,1)
    job_service.patch_job(db,current_user=db.get(User,4),job_id=job.id,
                          payload=JobUpdate(expected_version=1,title="CHANGED"))
    with client_for(db,8) as manager:
        assert manager.post(f"/api/v1/assignments/{task.id}/accept",json={"expected_round":1}).status_code == 409
        assert manager.post(f"/api/v1/assignments/{task.id}/decline",json={"expected_round":1,"reason":"岗位已变更"}).status_code == 200


def test_pause_preserves_contacts_but_blocks_match_and_acceptance(assignment_db):
    db = assignment_db
    job, task_id, candidate_id = active_agency_task(db)
    second = invite(db,4,job.id,2)
    job_service.change_job_status(db,current_user=db.get(User,4),job_id=job.id,
                                  expected_version=1,target_status=JobStatus.suspended,reason="暂停寻访")
    with client_for(db,10) as owner, client_for(db,9) as invited:
        assert owner.get(f"/api/v1/jobs/{job.id}").json()["contact_info"] == "CLIENT_PRIVATE_CONTACT"
        assert owner.get(f"/api/v1/assignments/{task_id}").json()["contact_info"] == "CLIENT_PRIVATE_CONTACT"
        assert invited.post(f"/api/v1/assignments/{second.id}/accept",json={"expected_round":1}).status_code == 409
    with patch.object(match_service.llm,"chat") as model:
        with pytest.raises(HTTPException):
            match_service.run_match(db,current_user=db.get(User,10),payload=match_payload(db,job.id,candidate_id))
        model.assert_not_called()


def test_reinvite_preserves_previous_round_snapshot(assignment_db):
    db = assignment_db
    job, task_id, _ = active_agency_task(db)
    job_service.patch_job(db,current_user=db.get(User,4),job_id=job.id,
                          payload=JobUpdate(expected_version=1,title="NEW_TERMS"))
    job_service.confirm_job(db,current_user=db.get(User,4),job_id=job.id,expected_version=2)
    invite(db,4,job.id,1,version=2)
    events = assignment_service.list_assignment_events(db,db.get(User,8),task_id)
    previous = events[-1].payload["previous_round"]
    assert previous["round_no"] == 1 and previous["job_version"] == 1
    assert previous["owner_user_id"] == 10 and previous["invited_by"] == 4
    assert previous["accepted_by"] == 8 and previous["job_snapshot"]["title"] == "AI 算法工程师"
    assert "CLIENT_PRIVATE_CONTACT" not in str(previous)
    with client_for(db,10) as former_owner:
        assert former_owner.get(f"/api/v1/assignments/{task_id}").status_code == 404
        assert former_owner.get("/api/v1/assignments").json() == []


def test_exit_transfers_candidates_and_all_tasks_atomically(assignment_db):
    db = assignment_db
    job, task_id, candidate_id = active_agency_task(db)
    before = db.query(AssignmentEvent).count()
    agency_service.leave_member(db,db.get(User,10),1,21,MemberLeave(transfer_to_user_id=8))
    assert db.get(AgencyMember,21).status == "left"
    assert db.get(Candidate,candidate_id).owner_user_id == 8
    assert db.get(Candidate,candidate_id).created_by == 10
    assert db.get(JobAssignment,task_id).owner_user_id == 8
    assert db.query(AssignmentEvent).count() == before+1


def test_exit_failure_rolls_back_candidate_task_member_and_event(assignment_db):
    db = assignment_db
    _, task_id, candidate_id = active_agency_task(db)
    before = db.query(AssignmentEvent).count()
    def reject_exit(session, *_):
        if any(isinstance(row,AssignmentEvent) and row.payload.get("reason")=="agency_member_exit" for row in session.new):
            raise RuntimeError("INJECTED_EXIT_EVENT_FAILURE")
    event.listen(db,"before_flush",reject_exit)
    try:
        with pytest.raises(RuntimeError,match="INJECTED_EXIT_EVENT_FAILURE"):
            agency_service.leave_member(db,db.get(User,10),1,21,MemberLeave(transfer_to_user_id=8))
    finally:
        event.remove(db,"before_flush",reject_exit)
    assert db.get(AgencyMember,21).status == "active"
    assert db.get(Candidate,candidate_id).owner_user_id == 10
    assert db.get(JobAssignment,task_id).owner_user_id == 10
    assert db.query(AssignmentEvent).count() == before


@pytest.mark.parametrize("change", ["cancel","version","owner","disabled","agency_disabled","pause","role_changed"])
def test_model_reply_cannot_save_after_authorization_changes(assignment_db, change):
    db = assignment_db
    job, task_id, candidate_id = active_agency_task(db)
    job_id = job.id
    before = db.query(MatchAnalysis).count()
    def change_and_reply(*_):
        if change=="cancel":
            assignment_service.end_assignment(db,db.get(User,4),task_id,expected_round=1,complete=False,reason="撤权")
        elif change=="version":
            job_service.patch_job(db,current_user=db.get(User,4),job_id=job_id,payload=JobUpdate(expected_version=1,title="CHANGED"))
        elif change=="owner":
            assignment_service.transfer_owner(db,db.get(User,8),task_id,expected_round=1,expected_owner_user_id=10,owner_user_id=8)
        elif change=="disabled":
            db.get(User,10).enabled=False
            db.commit()
        elif change=="agency_disabled":
            db.get(Agency,1).status="disabled"
            db.commit()
        elif change=="role_changed":
            db.get(User,10).role=UserRole.admin
            db.commit()
        else:
            job_service.change_job_status(db,current_user=db.get(User,4),job_id=job_id,expected_version=1,target_status=JobStatus.suspended,reason="暂停")
        return VALID_MATCH
    with patch.object(match_service.llm,"chat",side_effect=change_and_reply):
        with pytest.raises(HTTPException) as error:
            match_service.run_match(db,current_user=db.get(User,10),payload=match_payload(db,job_id,candidate_id))
    assert error.value.status_code in (403,409)
    assert db.query(MatchAnalysis).count() == before


def test_both_candidate_and_task_permissions_are_required(assignment_db):
    db = assignment_db
    job, task_id, candidate_id = active_agency_task(db,owner=8)
    db.get(Candidate,candidate_id).owner_user_id=10
    db.commit()
    with patch.object(match_service.llm,"chat") as model:
        with pytest.raises(HTTPException):
            match_service.run_match(db,current_user=db.get(User,10),payload=match_payload(db,job.id,candidate_id))
        model.assert_not_called()
    assignment_service.transfer_owner(db,db.get(User,8),task_id,expected_round=1,expected_owner_user_id=8,owner_user_id=10)
    db.get(Candidate,candidate_id).owner_user_id=8
    db.commit()
    with patch.object(match_service.llm,"chat") as model:
        with pytest.raises(HTTPException):
            match_service.run_match(db,current_user=db.get(User,10),payload=match_payload(db,job.id,candidate_id))
        model.assert_not_called()


def test_profile_is_immutable_and_same_terms_do_not_bump_version(assignment_db):
    db = assignment_db
    job = create_confirmed_job(db)
    profile_id, original = job.job_profile_id, db.get(JobProfile,job.job_profile_id).raw_content
    job = job_service.patch_job(db,current_user=db.get(User,4),job_id=job.id,
                                payload=JobUpdate(expected_version=1,title=job.title))
    assert job.version == 1 and job.confirmed_at is not None
    assert job.job_profile_id == profile_id and db.get(JobProfile,profile_id).raw_content == original


def test_admin_cannot_complete_on_behalf_of_customer(assignment_db):
    db = assignment_db
    _, task_id, _ = active_agency_task(db)
    with client_for(db,1) as admin:
        assert admin.post(f"/api/v1/assignments/{task_id}/complete",json={"expected_round":1,"reason":"代签"}).status_code == 403


def test_admin_can_inspect_matches_but_cannot_generate_business_match(assignment_db):
    db = assignment_db
    job, _, candidate_id = active_agency_task(db)
    with patch.object(match_service.llm,"chat") as model:
        with pytest.raises(HTTPException) as error:
            match_service.run_match(db,current_user=db.get(User,1),
                                    payload=match_payload(db,job.id,candidate_id))
    assert error.value.status_code == 403
    model.assert_not_called()


def test_suspended_active_assignment_stays_authorized_for_existing_work(assignment_db):
    db = assignment_db
    job, task_id, _ = active_agency_task(db)
    job_service.change_job_status(db,current_user=db.get(User,4),job_id=job.id,
                                  expected_version=1,target_status=JobStatus.suspended,reason="暂停")
    with client_for(db,10) as owner:
        task = owner.get(f"/api/v1/assignments/{task_id}").json()
        job_detail = owner.get(f"/api/v1/jobs/{job.id}").json()
    assert task["has_current_authorization"] is True
    assert job_detail["has_current_authorization"] is True


def test_pause_keeps_active_task_contact_access(assignment_db):
    db = assignment_db
    job, task_id, _ = active_agency_task(db)
    job_service.change_job_status(db,current_user=db.get(User,4),job_id=job.id,
                                  expected_version=1,target_status=JobStatus.suspended,reason="暂停")
    with client_for(db,8) as manager, client_for(db,10) as owner:
        assert manager.get(f"/api/v1/jobs/{job.id}").json()["contact_info"] == "CLIENT_PRIVATE_CONTACT"
        assert owner.get(f"/api/v1/jobs/{job.id}").json()["contact_info"] == "CLIENT_PRIVATE_CONTACT"


def test_manager_cannot_view_other_agency_or_inactive_task_events(assignment_db):
    db = assignment_db
    job = create_confirmed_job(db)
    task_a = invite(db,4,job.id,1)
    task_b = invite(db,4,job.id,2)
    with client_for(db,8) as first, client_for(db,9) as second:
        assert first.get(f"/api/v1/assignments/{task_b.id}").status_code == 404
        assert second.get(f"/api/v1/assignments/{task_a.id}/events").status_code == 404
        assert first.post(f"/api/v1/assignments/{task_a.id}/accept",json={"expected_round":1}).status_code == 200
    assignment_service.end_assignment(db,db.get(User,4),task_a.id,
                                      expected_round=1,complete=False,reason="撤权")
    with client_for(db,10) as former_owner:
        assert former_owner.get(f"/api/v1/assignments/{task_a.id}").status_code == 404
