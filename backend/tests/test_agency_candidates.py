import pytest
from unittest.mock import patch
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from datetime import datetime
from app.models import Agency, AgencyMember, Candidate, Job, JobAssignment, MatchAnalysis, ServiceProvider, User, UserRole
from app.services.candidate_access import can_access_candidate
from app.services import agency_service, match_service
from match_fixtures import match_payload, VALID_MATCH
from test_permissions import db, client_for


@pytest.fixture
def agency_db(db):
    for uid in (8, 9, 10):
        db.add(User(id=uid, username=f'agency_hunter_{uid}', password_hash='UNUSED_TEST_HASH',
                    role=UserRole.headhunter, enabled=True))
    db.commit()
    db.add_all([Agency(id=1, name='AGENCY_A', status='active', created_by=1),
                Agency(id=2, name='AGENCY_B', status='active', created_by=1)])
    db.flush()
    db.add_all([ServiceProvider(id=10, kind='agency', agency_id=1),
                ServiceProvider(id=11, kind='agency', agency_id=2)])
    db.add_all([
        AgencyMember(id=1, agency_id=1, user_id=8, role='manager', status='active', invited_by=1),
        AgencyMember(id=2, agency_id=1, user_id=2, role='staff', status='active', invited_by=8),
        AgencyMember(id=3, agency_id=1, user_id=3, role='staff', status='active', invited_by=8),
        AgencyMember(id=4, agency_id=2, user_id=9, role='manager', status='active', invited_by=1),
    ])
    db.flush()
    db.add_all([
        Candidate(id=40, name='AGENCY_CANDIDATE_A', created_by=2, provider_id=10, owner_user_id=2),
        Candidate(id=41, name='AGENCY_CANDIDATE_B', created_by=3, provider_id=10, owner_user_id=3),
        Candidate(id=42, name='OTHER_AGENCY', created_by=9, provider_id=11, owner_user_id=9),
    ])
    db.flush()
    db.add(MatchAnalysis(id=50, job_id=10, candidate_id=40, analysis_text='AGENCY_PRIVATE'))
    job = db.get(Job, 10)
    job.confirmed_by = 4
    job.confirmed_at = job.ever_confirmed_at = datetime(2026,1,1)
    db.add(JobAssignment(job_id=10, provider_id=10, status='active', job_version=1,
                         round_no=1, job_snapshot={'version':1,'title':'AUDIT_JOB_A'},
                         owner_user_id=2, invited_by=4, invited_at=datetime(2026,1,1),
                         accepted_by=8, accepted_at=datetime(2026,1,1)))
    db.commit()
    return db


@pytest.mark.parametrize('uid,allowed', [(1, True), (8, True), (2, True), (3, False), (9, False), (4, False)])
def test_current_owner_and_supervisor_visibility(agency_db, uid, allowed):
    db = agency_db
    assert can_access_candidate(db, db.get(User, uid), db.get(Candidate, 40)) == allowed


def test_list_count_and_detail_have_same_scope(agency_db):
    with client_for(agency_db, 2) as client:
        page = client.get('/api/v1/candidates', params={'size': 1})
        hidden = client.get('/api/v1/candidates/41')
        detail = client.get('/api/v1/candidates/40')
    assert page.status_code == detail.status_code == 200
    assert page.json()['total'] == 2  # personal 20 + assigned agency 40
    assert hidden.status_code == 403
    assert detail.json()['owner_username'] == 'audit_user_2'
    assert detail.json()['provider_kind'] == 'agency'


def test_transfer_revokes_original_creator_and_matching_access(agency_db):
    db = agency_db
    with client_for(db, 8) as client:
        response = client.post('/api/v1/candidates/40/transfer', json={'owner_user_id': 3})
    assert response.status_code == 200
    assert db.get(Candidate, 40).created_by == 2
    assert db.get(Candidate, 40).owner_user_id == 3
    with client_for(db, 2) as old, client_for(db, 3) as new:
        assert old.get('/api/v1/candidates/40').status_code == 403
        assert old.get('/api/v1/matches/50').status_code == 403
        assert 50 not in {r['id'] for r in old.get('/api/v1/matches').json()['items']}
        assert new.get('/api/v1/matches/50').status_code == 403
        assert 50 not in {r['id'] for r in new.get('/api/v1/matches').json()['items']}


@pytest.mark.parametrize('uid,target,status', [(2,3,403),(9,3,403),(8,9,409)])
def test_transfer_rejects_nonmanager_and_foreign_target(agency_db, uid, target, status):
    with client_for(agency_db, uid) as client:
        assert client.post('/api/v1/candidates/40/transfer', json={'owner_user_id':target}).status_code == status


def test_personal_asset_is_not_shared_with_institution(agency_db):
    db = agency_db
    assert not can_access_candidate(db, db.get(User, 8), db.get(Candidate, 20))
    with client_for(db, 8) as client:
        assert client.post('/api/v1/candidates/20/transfer', json={'owner_user_id': 3}).status_code == 409


@pytest.mark.parametrize('injection', [{'provider_id':10}, {'created_by':3}, {'owner_user_id':3}])
def test_plain_update_rejects_ownership_injection(agency_db, injection):
    with client_for(agency_db, 2) as client:
        assert client.patch('/api/v1/candidates/40', json=injection).status_code == 422


def test_create_personal_and_institutional_assets(agency_db):
    db = agency_db
    with client_for(db, 2) as client:
        individual = client.post('/api/v1/candidates', json={'name':'NEW_PERSONAL'})
        agency = client.post('/api/v1/candidates', json={'name':'NEW_AGENCY','ownership':'agency'})
        injected = client.post('/api/v1/candidates', json={'name':'INVALID','owner_user_id':3})
    assert individual.status_code == agency.status_code == 200
    assert individual.json()['provider_kind'] == 'individual'
    assert agency.json()['provider_id'] == 10
    assert agency.json()['owner_user_id'] == agency.json()['created_by'] == 2
    assert injected.status_code == 403


def test_invitation_requires_target_acceptance(agency_db):
    db = agency_db
    with client_for(db, 8) as manager:
        invited = manager.post('/api/v1/agencies/1/invitations', json={'username':'agency_hunter_10'})
        assert invited.status_code == 201
        member_id = invited.json()['id']
        assert manager.post(f'/api/v1/agencies/1/members/{member_id}/decision', json={'accept':True}).status_code == 403
    with client_for(db, 10) as target:
        context = target.get('/api/v1/agencies/context').json()
        assert context['membership'] is None and len(context['invitations']) == 1
        assert target.post(f'/api/v1/agencies/1/members/{member_id}/decision', json={'accept':True}).status_code == 200
        assert target.get('/api/v1/agencies/context').json()['membership']['status'] == 'active'


def test_duplicate_invitation_returns_409_without_partial_write(agency_db):
    db = agency_db
    with client_for(db, 8) as manager:
        assert manager.post('/api/v1/agencies/1/invitations', json={'username':'agency_hunter_10'}).status_code == 201
        assert manager.post('/api/v1/agencies/1/invitations', json={'username':'agency_hunter_10'}).status_code == 409
    assert db.query(AgencyMember).filter_by(user_id=10).count() == 1


def test_two_pending_agency_invitations_only_one_can_be_accepted(agency_db):
    db = agency_db
    with client_for(db, 8) as a, client_for(db, 9) as b:
        first = a.post('/api/v1/agencies/1/invitations', json={'username':'agency_hunter_10'}).json()['id']
        second = b.post('/api/v1/agencies/2/invitations', json={'username':'agency_hunter_10'}).json()['id']
    with client_for(db, 10) as user:
        assert user.post(f'/api/v1/agencies/1/members/{first}/decision', json={'accept':True}).status_code == 200
        assert user.post(f'/api/v1/agencies/2/members/{second}/decision', json={'accept':True}).status_code == 409


def test_member_exit_moves_agency_assets_but_preserves_personal_assets(agency_db):
    db = agency_db
    with client_for(db, 2) as user:
        assert user.post('/api/v1/agencies/1/members/2/leave', json={}).status_code == 409
        assert user.post('/api/v1/agencies/1/members/2/leave', json={'transfer_to_user_id':3}).status_code == 200
        assert user.get('/api/v1/candidates/40').status_code == 403
        assert user.get('/api/v1/candidates/20').status_code == 200
    assert db.get(Candidate, 40).owner_user_id == 3
    assert db.get(Candidate, 40).created_by == 2


def test_last_manager_protection_and_successor(agency_db):
    with client_for(agency_db, 8) as user:
        assert user.post('/api/v1/agencies/1/members/1/leave', json={}).status_code == 409
        assert user.patch('/api/v1/agencies/1/members/1/role', json={'role':'staff'}).status_code == 409
        assert user.patch('/api/v1/agencies/1/members/3/role', json={'role':'manager'}).status_code == 200
        assert user.post('/api/v1/agencies/1/members/1/leave', json={}).status_code == 200


def test_agency_disable_revokes_institution_only(agency_db):
    db = agency_db
    with client_for(db, 1) as admin:
        assert admin.patch('/api/v1/agencies/1/status', json={'status':'disabled'}).status_code == 200
    with client_for(db, 2) as user:
        assert user.get('/api/v1/candidates/40').status_code == 403
        assert user.get('/api/v1/candidates/20').status_code == 200


def test_disabled_member_cannot_read_even_via_service(agency_db):
    db = agency_db
    user = db.get(User, 2)
    user.enabled = False
    db.commit()
    assert not can_access_candidate(db, user, db.get(Candidate, 40))


def test_database_blocks_two_active_agencies(agency_db):
    db = agency_db
    db.add(AgencyMember(agency_id=2, user_id=2, role='staff', status='active', invited_by=9))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_invalid_provider_xor_rejected(agency_db):
    agency_db.add(ServiceProvider(kind='individual', user_id=10, agency_id=1))
    with pytest.raises(IntegrityError):
        agency_db.commit()
    agency_db.rollback()


def test_public_responses_do_not_expose_credentials(agency_db):
    with client_for(agency_db, 8) as user:
        members = user.get('/api/v1/agencies/1/members')
        assert members.status_code == 200
        assert 'password_hash' not in members.text
        assert 'security_answers' not in members.text


def test_unknown_historical_candidate_only_admin_can_see(agency_db):
    db = agency_db
    assert db.get(Candidate,22).provider_id is None
    with client_for(db, 2) as user, client_for(db, 1) as admin:
        assert user.get('/api/v1/candidates/22').status_code == 403
        assert admin.get('/api/v1/candidates/22').status_code == 200


def test_create_agency_requires_admin_and_rolls_back_on_conflict(agency_db):
    db = agency_db
    with client_for(db, 8) as user, client_for(db, 1) as admin:
        assert user.post('/api/v1/agencies', json={'name':'UNVERIFIED','manager_user_id':10}).status_code == 403
        assert admin.post('/api/v1/agencies', json={'name':'NEW','manager_user_id':10}).status_code == 201
        assert admin.post('/api/v1/agencies', json={'name':'DUPLICATE','manager_user_id':10}).status_code == 409
    assert db.query(Agency).count() == 3


def test_permission_revoked_during_model_call_does_not_save_result(agency_db):
    db = agency_db
    count_before = db.query(MatchAnalysis).count()
    def revoke_and_respond(*args):
        db.get(Candidate,40).owner_user_id = 3
        db.commit()
        return VALID_MATCH
    with patch.object(match_service.llm,'chat',side_effect=revoke_and_respond):
        with pytest.raises(HTTPException) as error:
            match_service.run_match(db,current_user=db.get(User,2),
                                    payload=match_payload(db,10,40))
    assert error.value.status_code == 403
    assert db.query(MatchAnalysis).count() == count_before


def test_disabled_account_cannot_create_agency_via_service(agency_db):
    db = agency_db
    admin = db.get(User,1)
    admin.enabled = False
    db.commit()
    with pytest.raises(HTTPException) as error:
        agency_service.create_agency(db,admin,SimpleNamespace(name='BLOCKED',manager_user_id=10))
    assert error.value.status_code == 403
    assert db.query(Agency).count() == 2
