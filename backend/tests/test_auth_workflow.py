"""真实认证路由回归，使用隔离SQLite，不加载正式配置。"""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.v1.endpoints import auth, users
from app.core.config import settings
from app.models import Company, User
from app.models.user_security_answer import UserSecurityAnswer
from app.services import auth_service
from test_permissions import db


@pytest.fixture
def auth_client(db, monkeypatch):
    for key, value in dict(SECRET_KEY='ISOLATED_TEST_KEY_NOT_A_REAL_SECRET',
                           ALGORITHM='HS256', ACCESS_TOKEN_EXPIRE_MINUTES=30,
                           RESET_MAX_FAILED=5, RESET_LOCK_MINUTES=15).items():
        monkeypatch.setattr(settings, key, value, raising=False)
    app = FastAPI()
    app.include_router(auth.router, prefix='/api/v1')
    app.include_router(users.router, prefix='/api/v1')
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client


def registration(role='headhunter'):
    data = dict(username='workflow_new_user', password='TEST_PASSWORD_ONLY', role=role,
                security_answers=[dict(question_code=code, answer='TEST_ANSWER_ONLY')
                    for code in ['primary_school', 'mother_name', 'birth_city']])
    if role == 'recruiter':
        data['company_name'] = 'WORKFLOW_NEW_COMPANY'
    return data


@pytest.mark.parametrize('role', ['recruiter', 'headhunter'])
def test_failed_security_answers_leave_no_partial_registration(db, role):
    payload = auth_service.UserCreate(**registration(role))
    before = (db.query(Company).count(), db.query(User).count())
    with patch.object(auth_service.user_crud, 'create_security_answers',
                      side_effect=RuntimeError('INJECTED_REGISTRATION_FAILURE')):
        with pytest.raises(RuntimeError):
            auth_service.register_user(db, payload)
    # 重新开启事务读取，不能被会话中残留对象掩盖。
    db.rollback()
    assert (db.query(Company).count(), db.query(User).count()) == before
    assert db.query(User).filter_by(username=payload.username).first() is None
    # 失败后使用同一用户名/企业名可重试。
    user = auth_service.register_user(db, payload)
    assert db.query(UserSecurityAnswer).filter_by(user_id=user.id).count() == 3


def test_failure_after_answer_flush_rolls_back_all_rows(db):
    payload = auth_service.UserCreate(**registration('recruiter'))
    before = (db.query(Company).count(), db.query(User).count(),
              db.query(UserSecurityAnswer).count())
    original = auth_service.user_crud.create_security_answers

    def flushed_then_failed(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('INJECTED_AFTER_ANSWER_FLUSH')

    with patch.object(auth_service.user_crud, 'create_security_answers',
                      side_effect=flushed_then_failed):
        with pytest.raises(RuntimeError):
            auth_service.register_user(db, payload)
    assert (db.query(Company).count(), db.query(User).count(),
            db.query(UserSecurityAnswer).count()) == before
    assert auth_service.register_user(db, payload).username == payload.username


def test_database_username_conflict_rolls_back_new_company(db):
    from fastapi import HTTPException
    payload = registration('recruiter')
    payload['username'] = 'audit_user_2'
    before = (db.query(Company).count(), db.query(User).count())
    # 绕过接口预检查，验证数据库唯一冲突的兜底与事务回滚。
    with pytest.raises(HTTPException) as error:
        auth_service.register_user(db, auth_service.UserCreate(**payload))
    assert error.value.status_code == 409
    assert (db.query(Company).count(), db.query(User).count()) == before


@pytest.mark.parametrize('role', ['headhunter', 'recruiter', 'jobseeker'])
def test_registration_login_and_password_recovery(auth_client, db, role):
    payload = registration(role)
    response = auth_client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 200
    user_id = response.json()['id']
    assert 'password_hash' not in response.json()
    user = db.get(User, user_id)
    assert user.password_hash != payload['password']
    assert db.query(UserSecurityAnswer).filter_by(user_id=user_id).count() == 3
    login = auth_client.post('/api/v1/auth/login', json={
        'username': payload['username'], 'password': payload['password']})
    assert login.status_code == 200
    # 不记录或打印token，只用于同一隔离请求。
    headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
    assert auth_client.get('/api/v1/users/me', headers=headers).json()['id'] == user_id
    questions = auth_client.get('/api/v1/auth/security-questions',
                                params={'username': payload['username']})
    assert questions.status_code == 200 and len(questions.json()['questions']) == 3
    assert all(set(q) == {'question_code', 'question_text'} for q in questions.json()['questions'])
    reset = dict(username=payload['username'], answers=payload['security_answers'],
                 new_password='NEW_TEST_PASSWORD_ONLY')
    assert auth_client.post('/api/v1/auth/password/reset', json=reset).status_code == 200
    assert auth_client.post('/api/v1/auth/login', json={
        'username': payload['username'], 'password': payload['password']}).status_code == 401
    assert auth_client.post('/api/v1/auth/login', data={
        'username': payload['username'], 'password': reset['new_password']}).status_code == 200


def test_wrong_answers_lock_and_disabled_account_stays_disabled(auth_client, db):
    payload = registration()
    response = auth_client.post('/api/v1/auth/register', json=payload)
    user = db.get(User, response.json()['id'])
    bad = dict(username=payload['username'], new_password='NEW_TEST_PASSWORD_ONLY',
               answers=[dict(a, answer='WRONG_TEST_ANSWER') for a in payload['security_answers']])
    for _ in range(4):
        assert auth_client.post('/api/v1/auth/password/reset', json=bad).status_code == 400
    assert auth_client.post('/api/v1/auth/password/reset', json=bad).status_code == 423
    good = dict(bad, answers=payload['security_answers'])
    assert auth_client.post('/api/v1/auth/password/reset', json=good).status_code == 423
    assert auth_service.authenticate_user(db, payload['username'], payload['password']) is not None
    user.reset_locked_until = None
    user.enabled = False
    db.commit()
    assert auth_client.post('/api/v1/auth/password/reset', json=good).status_code == 200
    assert auth_client.post('/api/v1/auth/login', json={
        'username': payload['username'], 'password': good['new_password']}).status_code == 403


def test_registration_rejects_admin_and_duplicate_questions(auth_client):
    payload = registration('admin')
    assert auth_client.post('/api/v1/auth/register', json=payload).status_code == 422
    payload = registration()
    payload['security_answers'][1] = payload['security_answers'][0]
    assert auth_client.post('/api/v1/auth/register', json=payload).status_code == 422
