"""真实模型封装接入业务接口，验证主备模型来源落库；网络由替身隔离。"""
from openai import OpenAIError
import pytest

from app.models import MatchAnalysis, ResumeSkill
from app.services import match_service, skill_service
from match_fixtures import VALID_MATCH
from test_llm_fallback import transport, _primary, _fallback, _ok
from test_permissions import db, client_for
from test_resume_skills import files, parsed, ai_skills


@pytest.mark.parametrize('use_fallback', [False, True], ids=['primary', 'fallback'])
def test_skill_and_match_store_actual_model(db, files, transport, monkeypatch, use_fallback):
    module, _, _ = transport
    monkeypatch.setattr(skill_service, 'llm', module)
    monkeypatch.setattr(match_service, 'llm', module)
    expected_model = 'fallback-model' if use_fallback else 'primary-model'
    if use_fallback:
        _primary(transport).side_effect = OpenAIError('SYNTHETIC_FAILURE')
    successful = _fallback(transport) if use_fallback else _primary(transport)
    successful.side_effect = [_ok(ai_skills()), _ok(VALID_MATCH)]

    with client_for(db, 2) as client:
        resume_id = parsed(client)
        skills = client.post(f'/api/v1/resumes/{resume_id}/extract-skills',
                             json={'expected_skill_revision': 0})
        assert skills.status_code == 200, skills.text
        assert skills.json()['items'][0]['model_used'] == expected_model
        assert db.query(ResumeSkill).filter_by(resume_id=resume_id).one().model_used == expected_model

        match = client.post('/api/v1/matches', json=dict(
            job_id=10, candidate_id=20, resume_id=resume_id,
            expected_job_version=1, expected_skill_revision=skills.json()['skill_revision']))
        assert match.status_code == 200, match.text
        record = db.get(MatchAnalysis, match.json()['id'])
        assert match.json()['model_used'] == expected_model
        assert record.model_used == expected_model
        assert record.input_snapshot['model_used'] == expected_model
