from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints import auth, jobs, matches
from app.core.database import Base
from app.models import Candidate, Company, CompanyRole, Job, JobAssignment, JobSource, MatchAnalysis, ServiceProvider, User, UserRole
from app.services import auth_service, job_service, match_service


@pytest.fixture
def db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    @event.listens_for(engine, 'connect')
    def enable_foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Company(id=1, name='AUDIT_CLIENT_A'), Company(id=2, name='AUDIT_CLIENT_B')])
        session.commit()
        roles = [(1, UserRole.admin, None), (2, UserRole.headhunter, None),
                 (3, UserRole.headhunter, None), (4, UserRole.recruiter, 1),
                 (5, UserRole.recruiter, 2), (6, UserRole.recruiter, None),
                 (7, UserRole.jobseeker, None), (14, UserRole.headhunter, None)]
        for uid, role, company in roles:
            session.add(User(id=uid, username=f'audit_user_{uid}', password_hash='UNUSED_TEST_HASH',
                             role=role, company_id=company,
                             company_role=CompanyRole.manager if role == UserRole.recruiter and company else None,
                             enabled=True))
        session.commit()
        session.add_all([
            Job(id=10, title='AUDIT_JOB_A', client_company_id=1, created_by=2, source=JobSource.headhunter_created,
                confirmed_by=4, confirmed_at=datetime(2026,1,1), ever_confirmed_at=datetime(2026,1,1)),
            Job(id=11, title='AUDIT_JOB_B', client_company_id=2, created_by=3, source=JobSource.headhunter_created,
                confirmed_by=5, confirmed_at=datetime(2026,1,1), ever_confirmed_at=datetime(2026,1,1)),
            Job(id=12, title='AUDIT_CLIENT_JOB', client_company_id=1, created_by=4, source=JobSource.client_published),
            Job(id=13, title='AUDIT_UNOWNED_JOB', client_company_id=1, created_by=None, source=JobSource.headhunter_created),
            Candidate(id=20, name='AUDIT_CANDIDATE_A', created_by=2),
            Candidate(id=21, name='AUDIT_CANDIDATE_B', created_by=3),
            Candidate(id=22, name='AUDIT_UNOWNED', created_by=None),
        ])
        session.commit()
        session.add_all([
            MatchAnalysis(id=30, job_id=10, candidate_id=20, analysis_text='AUDIT_PRIVATE_A'),
            MatchAnalysis(id=31, job_id=10, candidate_id=21, analysis_text='AUDIT_PRIVATE_B'),
            MatchAnalysis(id=32, job_id=11, candidate_id=20, analysis_text='AUDIT_PRIVATE_A2'),
            MatchAnalysis(id=33, job_id=10, candidate_id=22, analysis_text='AUDIT_UNOWNED'),
        ])
        session.commit()
        from migrations.backfill_ownership import backfill_candidate_ownership
        backfill_candidate_ownership(session)
        session.commit()
        provider2 = session.query(ServiceProvider).filter_by(user_id=2).one()
        provider3 = session.query(ServiceProvider).filter_by(user_id=3).one()
        session.add_all([
            JobAssignment(job_id=10, provider_id=provider2.id, status='active', job_version=1,
                          round_no=1, job_snapshot={'version':1,'title':'AUDIT_JOB_A'}, owner_user_id=2,
                          invited_by=4, invited_at=datetime(2026,1,1), accepted_by=2, accepted_at=datetime(2026,1,1)),
            JobAssignment(job_id=10, provider_id=provider3.id, status='active', job_version=1,
                          round_no=1, job_snapshot={'version':1,'title':'AUDIT_JOB_A'}, owner_user_id=3,
                          invited_by=4, invited_at=datetime(2026,1,1), accepted_by=3, accepted_at=datetime(2026,1,1)),
            JobAssignment(job_id=11, provider_id=provider2.id, status='active', job_version=1,
                          round_no=1, job_snapshot={'version':1,'title':'AUDIT_JOB_B'}, owner_user_id=2,
                          invited_by=5, invited_at=datetime(2026,1,1), accepted_by=2, accepted_at=datetime(2026,1,1)),
        ])
        session.commit()
        yield session
    engine.dispose()


def client_for(db, uid):
    app = FastAPI()
    from app.api.v1.endpoints import agencies, candidates, users
    from app.api.v1.endpoints import assignments
    from app.api.v1.endpoints import companies, resumes, delivery
    for router in [auth.router, jobs.router, matches.router, agencies.router, candidates.router,
                   assignments.router, assignments.provider_router, companies.router, resumes.router, delivery.router, users.router]:
        app.include_router(router, prefix='/api/v1')
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, uid)
    return TestClient(app)


def test_admin_user_list_filters_and_excludes_sensitive_fields(db):
    with client_for(db, 1) as client:
        response = client.get('/api/v1/users', params={'keyword': 'audit_user_4', 'role': 'recruiter'})
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 1
    assert data['items'][0]['username'] == 'audit_user_4'
    assert data['items'][0]['company_name'] == 'AUDIT_CLIENT_A'
    assert 'email' not in data['items'][0]
    assert 'phone' not in data['items'][0]
    assert 'password_hash' not in data['items'][0]


def test_company_manager_invites_unbound_recruiter_and_target_accepts(db):
    with client_for(db, 4) as manager:
        response = manager.post('/api/v1/companies/me/invitations', json={'username': 'audit_user_6'})
    assert response.status_code == 201
    invitation = response.json()
    assert invitation['status'] == 'pending'
    assert invitation['company_name'] == 'AUDIT_CLIENT_A'

    with client_for(db, 2) as unrelated_hunter:
        assert unrelated_hunter.post(
            f"/api/v1/companies/invitations/{invitation['id']}/decision", json={'accept': True}
        ).status_code == 404
    with client_for(db, 6) as invited_user:
        accepted = invited_user.post(
            f"/api/v1/companies/invitations/{invitation['id']}/decision", json={'accept': True}
        )
    assert accepted.status_code == 200
    assert accepted.json()['status'] == 'accepted'
    db.expire_all()
    assert db.get(User, 6).company_id == 1
    assert db.get(User, 6).company_role == CompanyRole.staff


def test_company_invitation_authorization_and_replay_guards(db):
    with client_for(db, 2) as unauthorized_hunter:
        assert unauthorized_hunter.post(
            '/api/v1/companies/me/invitations', json={'username': 'audit_user_6'}
        ).status_code == 403
    with client_for(db, 4) as manager:
        created = manager.post('/api/v1/companies/me/invitations', json={'username': 'audit_user_6'})
        invitation_id = created.json()['id']
        assert manager.post(
            '/api/v1/companies/me/invitations', json={'username': 'audit_user_6'}
        ).status_code == 409
        assert manager.post(
            f'/api/v1/companies/me/invitations/{invitation_id}/revoke'
        ).status_code == 200
        assert manager.post(
            f'/api/v1/companies/me/invitations/{invitation_id}/revoke'
        ).status_code == 409
    with client_for(db, 6) as invited_user:
        assert invited_user.post(
            f'/api/v1/companies/invitations/{invitation_id}/decision', json={'accept': True}
        ).status_code == 409


def test_only_manager_can_see_outgoing_invitations_and_members(db):
    with client_for(db, 4) as manager:
        invitation = manager.post(
            '/api/v1/companies/me/invitations', json={'username': 'audit_user_6'}
        ).json()
    with client_for(db, 5) as foreign_manager:
        assert foreign_manager.post(
            f"/api/v1/companies/me/invitations/{invitation['id']}/revoke"
        ).status_code == 404
    with client_for(db, 6) as staff:
        assert staff.get('/api/v1/companies/me/invitations').status_code == 403
        assert staff.get('/api/v1/companies/me/members').status_code == 403
        assert staff.get('/api/v1/companies/invitations').status_code == 200


def test_admin_user_list_paginates_enabled_filter(db):
    db.get(User, 3).enabled = False
    db.commit()
    with client_for(db, 1) as client:
        first = client.get('/api/v1/users', params={'enabled': 'true', 'page': 1, 'size': 2}).json()
        second = client.get('/api/v1/users', params={'enabled': 'true', 'page': 2, 'size': 2}).json()
    assert first['total'] == 7
    assert len(first['items']) == len(second['items']) == 2
    assert {row['id'] for row in first['items']}.isdisjoint({row['id'] for row in second['items']})


@pytest.mark.parametrize('uid', [2, 4, 7])
def test_non_admin_cannot_list_users(db, uid):
    with client_for(db, uid) as client:
        assert client.get('/api/v1/users').status_code == 403


@pytest.mark.parametrize('uid,job_id,expected', [
    (2, 11, 404), (2, 12, 404), (2, 13, 404), (2, 10, 404),
    (4, 10, 200), (4, 11, 404), (5, 10, 404), (1, 11, 200),
    (6, 10, 404), (7, 10, 403),
])
def test_job_update_access(db, uid, job_id, expected):
    before = db.get(Job, job_id).status
    with client_for(db, uid) as client:
        response = client.patch(f'/api/v1/jobs/{job_id}', json={'expected_version': 1, 'title': 'AUDIT_UPDATED'})
    assert response.status_code == expected
    db.expire_all()
    if expected == 200:
        assert db.get(Job, job_id).title == 'AUDIT_UPDATED'
    else:
        assert db.get(Job, job_id).status == before


def test_uninvited_hunter_cannot_view_foreign_job(db):
    with client_for(db, 14) as client:
        assert client.get('/api/v1/jobs/11').status_code == 404
        page = client.get('/api/v1/jobs')
        assert page.status_code == 200
        assert page.json()['total'] == 0
        assert page.json()['items'] == []


def test_unbound_recruiter_cannot_list_all_jobs(db):
    with client_for(db, 6) as client:
        assert client.get('/api/v1/jobs').status_code == 403


@pytest.mark.parametrize('uid,match_id,expected', [(2, 30, 200), (2, 31, 403),
    (2, 33, 403), (1, 31, 200), (4, 30, 403), (7, 30, 403), (2, 999, 404)])
def test_match_detail_access(db, uid, match_id, expected):
    with client_for(db, uid) as client:
        response = client.get(f'/api/v1/matches/{match_id}')
        assert response.status_code == expected
        if expected != 200:
            assert 'AUDIT_PRIVATE_B' not in response.text


@pytest.mark.parametrize('filters,expected_total,expected_ids', [
    ({}, 2, {30, 32}), ({'job_id': 10}, 1, {30}),
    ({'candidate_id': 21}, 0, set()), ({'job_id': 10, 'candidate_id': 21}, 0, set()),
])
def test_match_list_filters_before_count(db, filters, expected_total, expected_ids):
    with client_for(db, 2) as client:
        response = client.get('/api/v1/matches', params=filters)
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == expected_total
    assert {row['id'] for row in data['items']} == expected_ids


def test_match_pagination_keeps_private_total(db):
    with client_for(db, 2) as client:
        pages = [client.get('/api/v1/matches', params={'page': p, 'size': 1}).json() for p in [1, 2, 3]]
    assert [page['total'] for page in pages] == [2, 2, 2]
    assert {row['id'] for page in pages for row in page['items']} == {30, 32}
    assert pages[2]['items'] == []


def test_admin_match_list_keeps_all_records(db):
    with client_for(db, 1) as client:
        response = client.get('/api/v1/matches')
    assert response.status_code == 200
    assert response.json()['total'] == 4


def test_existing_company_registration_creates_nothing(db):
    payload = {
        'username': 'audit_new_recruiter', 'password': 'YOUR_TEST_PASSWORD_HERE',
        'role': 'recruiter', 'company_name': 'AUDIT_CLIENT_A',
        'security_answers': [
            {'question_code': code, 'answer': 'TEST_ANSWER'}
            for code in ['primary_school', 'mother_name', 'birth_city']],
    }
    with client_for(db, 2) as client, patch.object(auth_service.user_crud, 'create_user', return_value=db.get(User, 4)) as create, \
         patch.object(auth_service.user_crud, 'create_security_answers') as answers:
        response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 409
    create.assert_not_called()
    answers.assert_not_called()
    assert db.query(Company).count() == 2
    assert db.query(User).count() == 8


def test_company_name_whitespace_cannot_create_duplicate(db):
    payload = {
        'username': 'audit_space_recruiter', 'password': 'YOUR_TEST_PASSWORD_HERE',
        'role': 'recruiter', 'company_name': '  AUDIT_CLIENT_A  ',
        'security_answers': [
            {'question_code': code, 'answer': 'TEST_ANSWER'}
            for code in ['primary_school', 'mother_name', 'birth_city']],
    }
    with client_for(db, 2) as client:
        response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 409
    assert db.query(Company).count() == 2
    assert db.query(User).count() == 8


def test_blank_company_name_is_rejected(db):
    payload = {
        'username': 'audit_blank_recruiter', 'password': 'YOUR_TEST_PASSWORD_HERE',
        'role': 'recruiter', 'company_name': '   ',
        'security_answers': [
            {'question_code': code, 'answer': 'TEST_ANSWER'}
            for code in ['primary_school', 'mother_name', 'birth_city']],
    }
    with client_for(db, 2) as client:
        response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 400
    assert db.query(Company).count() == 2
    assert db.query(User).count() == 8


@pytest.mark.parametrize('role,existing', [(UserRole.recruiter, False),
    (UserRole.headhunter, True), (UserRole.jobseeker, True)])
def test_allowed_registration_keeps_role_behavior(role, existing):
    payload = NS(role=role, company_name='AUDIT_NEW_CLIENT', username='audit_new_user',
                 password='YOUR_TEST_PASSWORD_HERE', real_name=None, email=None, phone=None,
                 security_answers=[])
    with patch.object(auth_service.company_crud, 'get_company_by_name', return_value=NS(id=9) if existing else None) as lookup, \
         patch.object(auth_service.company_crud, 'create_company', return_value=NS(id=9)) as company, \
         patch.object(auth_service.user_crud, 'create_user', return_value=NS(id=99)) as create, \
         patch.object(auth_service.user_crud, 'create_security_answers'):
        auth_service.register_user(Mock(), payload)
    if role == UserRole.recruiter:
        company.assert_called_once()
        assert create.call_args.kwargs['company_id'] == 9
        assert create.call_args.kwargs['company_role'].value == 'manager'
    else:
        lookup.assert_not_called()
        company.assert_not_called()
        assert create.call_args.kwargs['company_id'] is None


def test_direct_service_rejects_foreign_match(db):
    with pytest.raises(HTTPException) as error:
        match_service.get_match_detail(db, current_user=db.get(User, 2), match_id=31)
    assert error.value.status_code == 403
