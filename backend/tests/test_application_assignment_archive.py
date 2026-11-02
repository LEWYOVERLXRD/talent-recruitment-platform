"""有效承接公开、投递建档与推荐复用的真实接口回归。"""
from datetime import datetime

import pytest
from sqlalchemy import event

from app.models import Agency, AgencyMember, Application, ApplicationRecordKind, Candidate, Job, JobAssignment, Resume, ServiceProvider, User
from app.services import jobseeker_service
from test_jobseeker_workflow import client_for
from test_permissions import db as db_fixture, client_for as internal_client


def setup_application(db):
    # 客户建档、两个猎头承接；录入人不是负责猎头。
    job = db.get(Job, 10)
    job.source, job.created_by = 'client_published', 4
    profile = jobseeker_service.get_or_create_profile(db, db.get(User, 7))
    resume = Resume(candidate_id=profile.id, file_path='fixture.txt', original_name='fixture.txt',
                    parsed_text='Python experience', parse_status='success', version=1, is_primary=True,
                    uploaded_by=7, extraction_status='success', skill_revision=2)
    db.add(resume)
    db.commit()
    assignment = db.query(JobAssignment).filter_by(job_id=10, owner_user_id=2).one()
    return profile, resume, assignment


def submit(db, resume, assignment):
    with client_for(db, 7) as seeker:
        return seeker.post('/api/v1/applications', json={
            'job_id': 10, 'resume_id': resume.id, 'assignment_id': assignment.id})


def test_client_created_job_visible_with_receiver_and_immediate_archive(db_fixture):
    db = db_fixture
    profile, resume, assignment = setup_application(db)
    with client_for(db, 7) as seeker:
        page = seeker.get('/api/v1/jobs').json()
        job = next(x for x in page['items'] if x['id'] == 10)
        assert job['source'] == 'client_published'
        assert len(job['receivers']) == 2
        assert all(set(x) == {'assignment_id', 'headhunter_name', 'provider_name', 'provider_kind'} for x in job['receivers'])
        assert seeker.get('/api/v1/jobs/10').status_code == 200
    created = submit(db, resume, assignment)
    assert created.status_code == 201, created.text
    application = db.get(Application, created.json()['id'])
    archive = db.get(Candidate, application.working_candidate_id)
    assert archive.id != profile.id and archive.provider_id == assignment.provider_id
    assert archive.owner_user_id == 2 and archive.candidate_user_id is None
    assert profile.candidate_user_id == 7 and profile.provider_id is None
    working_resume = db.get(Resume, application.working_resume_id)
    assert working_resume.candidate_id == archive.id and working_resume.parsed_text == resume.parsed_text
    # 不伪造已抽取技能，工作简历需独立抽取/核验。
    assert working_resume.extraction_status == 'pending' and working_resume.skill_revision == 0
    with client_for(db, 2) as owner:
        assert owner.get(f'/api/v1/candidates/{archive.id}').status_code == 200
        assert any(x['id'] == archive.id for x in owner.get('/api/v1/candidates').json()['items'])
        rows = owner.get('/api/v1/applications').json()
        assert rows[0]['working_candidate_id'] == archive.id
        assert rows[0]['assignment_id'] == assignment.id
    with client_for(db, 3) as other:
        assert other.get('/api/v1/applications').json() == []
        assert other.get(f'/api/v1/candidates/{archive.id}').status_code in (403, 404)
    with client_for(db, 4) as customer:
        assert customer.get('/api/v1/applications').status_code == 403
        assert customer.get(f'/api/v1/candidates/{archive.id}').status_code in (403, 404)
        assert customer.get('/api/v1/recommendations').json()['total'] == 0


@pytest.mark.parametrize('invalid', ['cancelled', 'invited', 'old_version', 'suspended', 'unconfirmed', 'disabled_owner'])
def test_invalid_assignments_hidden_and_cannot_apply(db_fixture, invalid):
    db = db_fixture
    _, resume, assignment = setup_application(db)
    others = db.query(JobAssignment).filter(JobAssignment.job_id == 10, JobAssignment.id != assignment.id).all()
    for other in others:
        other.status = 'cancelled'
    if invalid in ('cancelled', 'invited'):
        assignment.status = invalid
    elif invalid == 'old_version':
        assignment.job_version = 99
    elif invalid == 'suspended':
        db.get(Job, 10).status = 'suspended'
    elif invalid == 'unconfirmed':
        db.get(Job, 10).confirmed_at = None
        db.get(Job, 10).confirmed_by = None
    else:
        db.get(User, 2).enabled = False
    db.commit()
    with client_for(db, 7) as seeker:
        assert not any(x['id'] == 10 for x in seeker.get('/api/v1/jobs').json()['items'])
        assert seeker.get('/api/v1/jobs/10').status_code == 404
    assert submit(db, resume, assignment).status_code == 404
    assert db.query(Application).count() == 0


def test_target_is_selected_assignment_not_job_creator(db_fixture):
    db = db_fixture
    _, resume, first = setup_application(db)
    target = db.query(JobAssignment).filter_by(job_id=10, owner_user_id=3).one()
    response = submit(db, resume, target)
    assert response.status_code == 201, response.text
    row = db.get(Application, response.json()['id'])
    assert row.publisher_user_id == 3 and row.assignment_id == target.id
    with client_for(db, 2) as other:
        assert other.get('/api/v1/applications').json() == []
        assert other.post(f'/api/v1/applications/{row.id}/recommendation', json={'assignment_id': first.id}).status_code == 404
    second_response = submit(db, resume, first)
    assert second_response.status_code == 201, second_response.text
    assert second_response.json()['record_kind'] == 'duplicate'
    assert second_response.json()['visibility_message'] == '该人选已入库'


def test_second_hunter_gets_private_duplicate_record_without_candidate_copy(db_fixture):
    db = db_fixture
    profile, resume, first = setup_application(db)
    first_response = submit(db, resume, first)
    assert first_response.status_code == 201, first_response.text
    primary = db.get(Application, first_response.json()['id'])
    assert primary.record_kind == ApplicationRecordKind.primary
    assert primary.canonical_application_id == primary.id

    second = db.query(JobAssignment).filter_by(job_id=10, owner_user_id=3).one()
    candidate_count, resume_count = db.query(Candidate).count(), db.query(Resume).count()
    duplicate_response = submit(db, resume, second)
    assert duplicate_response.status_code == 201, duplicate_response.text
    duplicate = db.get(Application, duplicate_response.json()['id'])
    assert duplicate.record_kind == ApplicationRecordKind.duplicate
    assert duplicate.canonical_application_id == primary.id
    assert duplicate.working_candidate_id is None and duplicate.working_resume_id is None
    assert (db.query(Candidate).count(), db.query(Resume).count()) == (candidate_count, resume_count)
    assert duplicate_response.json()['visibility_message'] == '该人选已入库'

    with client_for(db, 3) as second_hunter:
        own_rows = second_hunter.get('/api/v1/applications').json()
        assert len(own_rows) == 1
        visible = own_rows[0]
        assert visible['record_kind'] == 'duplicate'
        assert visible['candidate_name'] == '该人选已入库'
        assert visible['candidate_id'] is None and visible['applicant_user_id'] is None
        assert visible['resume_id'] is None and visible['resume_name'] is None
        assert visible['client_company_name'] is None and visible['publisher_user_id'] is None
        assert visible['working_candidate_id'] is None and not visible['can_recommend']
        assert second_hunter.get(f"/api/v1/applications/{duplicate.id}/resume").status_code == 409
        assert second_hunter.post(f"/api/v1/applications/{duplicate.id}/recommendation",
                                  json={'assignment_id': second.id}).status_code == 409
        assert second_hunter.patch(f"/api/v1/applications/{duplicate.id}/status",
                                   json={'status': 'screening'}).status_code == 409
        assert second_hunter.post(f"/api/v1/applications/{duplicate.id}/review",
                                  json={'decision': 'not_recommended', 'review_note': 'duplicate'}).status_code == 409

    with client_for(db, 2) as first_hunter:
        assert [x['id'] for x in first_hunter.get('/api/v1/applications').json()] == [primary.id]
    assert submit(db, resume, second).status_code == 409
    assert db.query(Application).count() == 2
    assert db.get(Candidate, primary.working_candidate_id).candidate_user_id is None


def test_recommendation_reuses_archive_and_exact_assignment(db_fixture):
    db = db_fixture
    _, resume, assignment = setup_application(db)
    response = submit(db, resume, assignment)
    row = db.get(Application, response.json()['id'])
    count = db.query(Candidate).count()
    with client_for(db, 2) as owner:
        draft = owner.post(f'/api/v1/applications/{row.id}/recommendation', json={'assignment_id': assignment.id})
        assert draft.status_code == 201, draft.text
        assert draft.json()['candidate_id'] == row.working_candidate_id
        assert draft.json()['resume_id'] == row.working_resume_id
        assert db.query(Candidate).count() == count
        assert owner.post(f'/api/v1/applications/{row.id}/recommendation', json={'assignment_id': assignment.id}).status_code == 404
    with client_for(db, 4) as customer:
        assert customer.get(f"/api/v1/recommendations/{draft.json()['id']}").status_code == 404


def test_archive_failure_rolls_back_all_working_rows(db_fixture):
    db = db_fixture
    _, resume, assignment = setup_application(db)
    before = db.query(Candidate).count(), db.query(Resume).count()
    def fail_insert(*_):
        raise RuntimeError('synthetic application insert failure')
    event.listen(Application, 'before_insert', fail_insert)
    try:
        with pytest.raises(RuntimeError, match='synthetic'):
            jobseeker_service.create_application(db, db.get(User, 7), job_id=10,
                                                resume_id=resume.id, assignment_id=assignment.id)
    finally:
        event.remove(Application, 'before_insert', fail_insert)
    assert (db.query(Candidate).count(), db.query(Resume).count()) == before
    assert db.query(Application).count() == 0


def test_agency_owner_and_supervisor_can_see_archive_other_staff_cannot(db_fixture):
    db = db_fixture
    _, resume, assignment = setup_application(db)
    agency = Agency(name='AUDIT_AGENCY', status='active', created_by=1)
    db.add(agency)
    db.flush()
    db.add_all([AgencyMember(agency_id=agency.id, user_id=2, role='staff', status='active', invited_by=1),
                AgencyMember(agency_id=agency.id, user_id=3, role='manager', status='active', invited_by=1),
                AgencyMember(agency_id=agency.id, user_id=14, role='staff', status='active', invited_by=1)])
    provider = ServiceProvider(kind='agency', agency_id=agency.id)
    db.add(provider)
    db.flush()
    assignment.provider_id = provider.id
    db.commit()
    created = submit(db, resume, assignment)
    assert created.status_code == 201, created.text
    row = db.get(Application, created.json()['id'])
    for uid in (2, 3):
        with client_for(db, uid) as member:
            assert member.get(f'/api/v1/candidates/{row.working_candidate_id}').status_code == 200
    with client_for(db, 14) as colleague:
        assert colleague.get(f'/api/v1/candidates/{row.working_candidate_id}').status_code in (403, 404)
    with client_for(db, 3) as manager:
        assert manager.get('/api/v1/applications').json() == []


def test_assignment_display_contains_business_names(db_fixture):
    db = db_fixture
    setup_application(db)
    with internal_client(db, 2) as hunter:
        rows = hunter.get('/api/v1/assignments').json()
        row = next(x for x in rows if x['job_id'] == 10)
        assert row['job_title'] == 'AUDIT_JOB_A'
        assert row['client_company_name'] == 'AUDIT_CLIENT_A'
