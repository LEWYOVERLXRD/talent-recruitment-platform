"""客户招聘员工入企流程，使用隔离 SQLite 合成数据。"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.v1.endpoints import companies
from app.models import Company, CompanyInvitation, CompanyRole, User, UserRole
from app.services import auth_service
from test_permissions import db, client_for


def invite(db, manager_id=4):
    with client_for(db, manager_id) as client:
        response = client.post('/api/v1/companies/me/invitations', json={'username': 'audit_user_6'})
    assert response.status_code == 201
    return response.json()['id']


def decide(db, invitation_id, accept=True):
    with client_for(db, 6) as client:
        return client.post(f'/api/v1/companies/invitations/{invitation_id}/decision', json={'accept': accept})


def test_waiting_recruiter_registration_does_not_create_or_bind_company(db):
    payload = {
        'username': 'audit_waiting_staff', 'password': 'YOUR_TEST_PASSWORD_HERE',
        'role': 'recruiter', 'company_join_mode': 'invited',
        'security_answers': [
            {'question_code': code, 'answer': 'TEST_ANSWER'}
            for code in ['primary_school', 'mother_name', 'birth_city']],
    }
    with client_for(db, 1) as client, patch.object(auth_service.user_crud, 'create_security_answers'):
        response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data['role'] == 'recruiter'
    assert data['company_id'] is None and data['company_role'] is None
    assert db.query(Company).count() == 2
    with client_for(db, data['id']) as waiting:
        assert waiting.get('/api/v1/jobs').status_code == 403
        assert waiting.get('/api/v1/companies/invitations').json() == []


def test_expired_invitation_cannot_be_accepted_and_can_be_replaced(db):
    old_id = invite(db)
    db.get(CompanyInvitation, old_id).expires_at = datetime.now() - timedelta(seconds=1)
    db.commit()
    with client_for(db, 6) as client:
        assert client.get('/api/v1/companies/invitations').json()[0]['status'] == 'expired'
    new_id = invite(db)
    assert new_id != old_id
    assert db.get(CompanyInvitation, old_id).status == 'expired'
    assert decide(db, old_id).status_code == 409
    assert decide(db, new_id).status_code == 200


def test_expired_decision_changes_no_company(db):
    invitation_id = invite(db)
    db.get(CompanyInvitation, invitation_id).expires_at = datetime.now() - timedelta(seconds=1)
    db.commit()
    assert decide(db, invitation_id).status_code == 409
    assert db.get(User, 6).company_id is None


def test_two_enterprises_can_invite_but_only_one_can_be_joined(db):
    first, second = invite(db, 4), invite(db, 5)
    assert decide(db, first).status_code == 200
    assert decide(db, second).status_code == 409
    assert db.get(User, 6).company_id == 1
    with client_for(db, 6) as client:
        assert client.get('/api/v1/jobs').status_code == 200
        assert client.get('/api/v1/companies/me/members').status_code == 403
        assert client.post('/api/v1/jobs/10/confirm', json={'expected_version': 1}).status_code == 403


@pytest.mark.parametrize('change', ['disabled', 'demoted', 'moved'])
def test_inviter_must_still_be_active_company_manager(db, change):
    invitation_id = invite(db)
    manager = db.get(User, 4)
    if change == 'disabled':
        manager.enabled = False
    elif change == 'demoted':
        manager.company_role = CompanyRole.staff
    else:
        manager.company_id = 2
    db.commit()
    assert decide(db, invitation_id).status_code == 409
    assert db.get(User, 6).company_id is None


def test_decline_preserves_history_and_allows_reinvitation(db):
    invitation_id = invite(db)
    response = decide(db, invitation_id, accept=False)
    assert response.status_code == 200 and response.json()['status'] == 'declined'
    assert decide(db, invitation_id).status_code == 409
    assert db.get(User, 6).company_id is None
    assert invite(db) != invitation_id


def test_current_manager_can_replace_invitation_from_demoted_inviter(db):
    old_id = invite(db)
    db.get(User, 4).company_role = CompanyRole.staff
    db.add(User(id=17, username='audit_new_manager', role=UserRole.recruiter,
                company_id=1, company_role=CompanyRole.manager,
                password_hash='UNUSED_TEST_HASH', enabled=True))
    db.commit()
    replacement = invite(db, 17)
    assert replacement != old_id
    assert db.get(CompanyInvitation, old_id).status == 'revoked'
    assert decide(db, replacement).status_code == 200


@pytest.mark.parametrize('username,expected', [
    ('audit_user_2', 404), ('audit_user_7', 404), ('audit_user_5', 409), ('missing_account', 404),
])
def test_invitation_rejects_ineligible_target(db, username, expected):
    with client_for(db, 4) as client:
        assert client.post('/api/v1/companies/me/invitations', json={'username': username}).status_code == expected
    assert db.query(CompanyInvitation).count() == 0


def test_invitation_lists_are_scoped_and_no_credentials_are_returned(db):
    invite(db)
    with client_for(db, 5) as foreign:
        assert foreign.get('/api/v1/companies/me/invitations').json() == []
        assert foreign.get('/api/v1/companies/invitations').json() == []
    with client_for(db, 6) as target:
        data = target.get('/api/v1/companies/invitations').json()
    assert len(data) == 1
    assert not {'password_hash', 'email', 'phone', 'security_answers'} & data[0].keys()


def test_anonymous_invitations_require_authentication(db):
    app = FastAPI()
    app.include_router(companies.router, prefix='/api/v1')
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        assert client.get('/api/v1/companies/invitations').status_code == 401
        assert client.post('/api/v1/companies/me/invitations', json={'username': 'audit_user_6'}).status_code == 401
