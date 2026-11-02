from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.v1.endpoints import companies
from app.models import Company, CompanyRole, User, UserRole
from test_permissions import client_for, db


@pytest.fixture
def company_data(db):
    db.add_all([Company(id=3, name='空企业'), Company(id=4, name='特殊%_企业')])
    db.add_all([
        User(id=17, username='company_staff', real_name='招聘员工', role=UserRole.recruiter,
             company_id=1, company_role=CompanyRole.staff, enabled=True, password_hash='UNUSED_TEST_HASH'),
        User(id=18, username='disabled_manager', role=UserRole.recruiter,
             company_id=1, company_role=CompanyRole.manager, enabled=False, password_hash='UNUSED_TEST_HASH'),
        User(id=19, username='legacy_non_recruiter', role=UserRole.headhunter,
             company_id=1, company_role=CompanyRole.manager, enabled=True, password_hash='UNUSED_TEST_HASH'),
    ])
    db.commit()
    return db


def test_company_list_paginates_filters_and_counts_recruiters_only(company_data):
    with client_for(company_data, 1) as client:
        first = client.get('/api/v1/companies', params={'size': 2}).json()
        second = client.get('/api/v1/companies', params={'size': 2, 'page': 2}).json()
        filtered = client.get('/api/v1/companies', params={'keyword': '  CLIENT_A  '}).json()
    assert first['total'] == second['total'] == 4
    assert [row['id'] for row in first['items']] == [4, 3]
    assert [row['id'] for row in second['items']] == [2, 1]
    assert filtered['total'] == 1
    row = filtered['items'][0]
    assert row['member_count'] == 3
    assert row['manager_count'] == 2
    assert row['enabled_manager_count'] == 1
    assert set(row) == {'id', 'name', 'created_at', 'member_count', 'manager_count', 'enabled_manager_count'}


@pytest.mark.parametrize('keyword,ids', [('%_', [4]), ('不存在', []), ('   ', [4, 3, 2, 1])])
def test_company_name_search_is_literal(company_data, keyword, ids):
    with client_for(company_data, 1) as client:
        data = client.get('/api/v1/companies', params={'keyword': keyword}).json()
    assert [row['id'] for row in data['items']] == ids
    assert data['total'] == len(ids)


def test_empty_company_and_missing_company_are_distinct(company_data):
    with client_for(company_data, 1) as client:
        detail = client.get('/api/v1/companies/3')
        members = client.get('/api/v1/companies/3/members')
        assert client.get('/api/v1/companies/999').status_code == 404
        assert client.get('/api/v1/companies/999/members').status_code == 404
    assert detail.status_code == members.status_code == 200
    assert detail.json()['member_count'] == detail.json()['enabled_manager_count'] == 0
    assert members.json() == {'total': 0, 'items': []}


def test_company_member_filters_pagination_and_field_whitelist(company_data):
    with client_for(company_data, 1) as client:
        page = client.get('/api/v1/companies/1/members', params={'size': 1, 'page': 2}).json()
        staff = client.get('/api/v1/companies/1/members', params={'company_role': 'staff', 'keyword': ' 招聘 '}).json()
        disabled = client.get('/api/v1/companies/1/members', params={'enabled': False, 'company_role': 'manager'}).json()
        missing = client.get('/api/v1/companies/1/members', params={'keyword': '%'}).json()
        foreign = client.get('/api/v1/companies/2/members').json()
    assert page['total'] == 3
    assert [row['id'] for row in page['items']] == [17]
    assert staff['total'] == 1 and staff['items'][0]['id'] == 17
    assert disabled['total'] == 1 and disabled['items'][0]['id'] == 18
    assert missing == {'total': 0, 'items': []}
    assert [row['id'] for row in foreign['items']] == [5]
    assert set(staff['items'][0]) == {'id', 'username', 'real_name', 'company_role', 'enabled', 'created_at'}


@pytest.mark.parametrize('uid', [2, 4, 6, 7, 17])
@pytest.mark.parametrize('path', ['/api/v1/companies', '/api/v1/companies/1', '/api/v1/companies/1/members'])
def test_company_admin_routes_reject_all_other_roles(company_data, uid, path):
    with client_for(company_data, uid) as client:
        response = client.get(path)
    assert response.status_code == 403
    assert 'AUDIT_CLIENT_A' not in response.text


@pytest.mark.parametrize('path', ['/api/v1/companies', '/api/v1/companies/1', '/api/v1/companies/1/members'])
def test_company_admin_routes_require_active_login(company_data, path):
    app = FastAPI()
    app.include_router(companies.router, prefix='/api/v1')
    app.dependency_overrides[get_db] = lambda: company_data
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        company_data.get(User, 1).enabled = False
        company_data.commit()
        with patch('app.api.deps.decode_access_token', return_value='1'):
            assert client.get(path, headers={'Authorization': 'Bearer TEST_PLACEHOLDER'}).status_code == 401


@pytest.mark.parametrize('params', [{'page': 0}, {'size': 0}, {'size': 101}, {'keyword': 'x' * 101}])
@pytest.mark.parametrize('path', ['/api/v1/companies', '/api/v1/companies/1/members'])
def test_company_admin_pagination_validates_bounds(company_data, path, params):
    with client_for(company_data, 1) as client:
        assert client.get(path, params=params).status_code == 422


def test_company_static_routes_still_work_and_admin_gets_do_not_mutate(company_data):
    before = [(u.id, u.company_id, u.company_role, u.enabled) for u in company_data.query(User).order_by(User.id)]
    with client_for(company_data, 4) as manager:
        assert manager.get('/api/v1/companies/me').json()['id'] == 1
        assert manager.get('/api/v1/companies/me/members').status_code == 200
        assert manager.get('/api/v1/companies/me/invitations').status_code == 200
        assert manager.get('/api/v1/companies/invitations').status_code == 200
    with client_for(company_data, 1) as admin:
        assert admin.get('/api/v1/companies/options').status_code == 200
        assert admin.get('/api/v1/companies').status_code == 200
        assert admin.get('/api/v1/companies/1').status_code == 200
        assert admin.get('/api/v1/companies/1/members').status_code == 200
    company_data.expire_all()
    assert company_data.query(Company).count() == 4
    assert before == [(u.id, u.company_id, u.company_role, u.enabled) for u in company_data.query(User).order_by(User.id)]
