"""真实封装的错误映射；客户端替身保证不发起网络请求。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException
from httpx import Request
from openai import APITimeoutError, OpenAIError
import pytest

from app.core.config import settings


@pytest.fixture
def transport(monkeypatch):
    for name, value in dict(LLM_API_KEY='YOUR_API_KEY_HERE', LLM_BASE_URL='https://example.invalid/v1',
                            LLM_TIMEOUT_SECONDS=60.0).items():
        monkeypatch.setattr(settings, name, value, raising=False)
    spec = importlib.util.spec_from_file_location('offline_llm_transport',
        Path(__file__).resolve().parents[1] / 'app/services/llm.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = Mock()
    monkeypatch.setattr(module, 'OpenAI', factory)
    return module, factory


def test_timeout_retry_and_actual_messages(transport):
    module, factory = transport
    factory.return_value.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='OFFLINE_RESULT'))])
    assert module.chat('SYSTEM_TEST', 'INPUT_TEST') == 'OFFLINE_RESULT'
    assert factory.call_args.kwargs['timeout'] == 60.0
    assert factory.call_args.kwargs['max_retries'] == 0
    assert factory.return_value.chat.completions.create.call_args.kwargs['messages'] == [
        {'role':'system','content':'SYSTEM_TEST'}, {'role':'user','content':'INPUT_TEST'}]


@pytest.mark.parametrize('kind,status', [('timeout',504),('sdk',502),('empty',502)])
def test_safe_transport_errors(transport, kind, status):
    module, factory = transport
    create = factory.return_value.chat.completions.create
    if kind == 'timeout':
        create.side_effect = APITimeoutError(request=Request('POST','https://example.invalid'))
    elif kind == 'sdk':
        create.side_effect = OpenAIError('SYNTHETIC_PRIVATE_DETAIL')
    else:
        create.return_value = SimpleNamespace(choices=[])
    with pytest.raises(HTTPException) as failure:
        module.chat('SYSTEM_TEST','INPUT_TEST')
    assert failure.value.status_code == status
    assert 'SYNTHETIC_PRIVATE_DETAIL' not in failure.value.detail
    assert 'example.invalid' not in failure.value.detail


def test_missing_config_does_not_create_client(transport, monkeypatch):
    module, factory = transport
    monkeypatch.setattr(settings, 'LLM_API_KEY','')
    with pytest.raises(HTTPException) as failure:
        module.chat('SYSTEM_TEST','INPUT_TEST')
    assert failure.value.status_code == 503
    factory.assert_not_called()


@pytest.mark.parametrize('content', [None, '', '   ', []])
def test_invalid_completion_content_is_safe_502(transport, content):
    module, factory = transport
    factory.return_value.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    with pytest.raises(HTTPException) as failure:
        module.chat('SYSTEM_TEST', 'INPUT_TEST')
    assert failure.value.status_code == 502
