"""模型降级逻辑：主模型失败自动切换备用模型，全部失败才返回错误。

与 test_llm_transport.py 相同，用 importlib 重新加载 llm 模块并用客户端替身，
保证全部测试不发起真实网络请求。
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException
from openai import APITimeoutError, OpenAIError
import pytest

from app.core.config import settings

PRIMARY_BASE = 'https://primary.invalid/v1'
FALLBACK_BASE = 'https://fallback.invalid/v1'


@pytest.fixture
def transport(monkeypatch):
    for name, value in dict(
        LLM_API_KEY='YOUR_API_KEY_HERE',
        LLM_BASE_URL=PRIMARY_BASE,
        LLM_MODEL='primary-model',
        LLM_FALLBACK_MODEL='fallback-model',
        LLM_FALLBACK_BASE_URL=FALLBACK_BASE,
        LLM_TIMEOUT_SECONDS=60.0,
    ).items():
        monkeypatch.setattr(settings, name, value, raising=False)
    spec = importlib.util.spec_from_file_location('offline_llm_fallback_transport',
        Path(__file__).resolve().parents[1] / 'app/services/llm.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clients = {PRIMARY_BASE: Mock(), FALLBACK_BASE: Mock()}
    factory = Mock(side_effect=lambda **kwargs: clients[kwargs['base_url']])
    module.OpenAI = factory
    return module, factory, clients


def _ok(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _primary(transport) -> Mock:
    return transport[2][PRIMARY_BASE].chat.completions.create


def _fallback(transport) -> Mock:
    return transport[2][FALLBACK_BASE].chat.completions.create


def test_primary_success_never_touches_fallback(transport):
    module, factory, _ = transport
    _primary(transport).return_value = _ok('PRIMARY_OK')
    assert module.chat('S', 'U') == 'PRIMARY_OK'
    assert factory.call_count == 1
    assert _fallback(transport).call_count == 0


def test_fallback_engaged_after_primary_sdk_error(transport):
    module, factory, _ = transport
    _primary(transport).side_effect = OpenAIError('SYNTHETIC_PRIVATE_DETAIL')
    _fallback(transport).return_value = _ok('FALLBACK_OK')
    assert module.chat('S', 'U') == 'FALLBACK_OK'
    assert factory.call_count == 2
    assert _fallback(transport).call_args.kwargs['model'] == 'fallback-model'


def test_fallback_engaged_after_primary_empty_content(transport):
    module, _, _ = transport
    _primary(transport).return_value = _ok('')
    _fallback(transport).return_value = _ok('FALLBACK_OK')
    assert module.chat('S', 'U') == 'FALLBACK_OK'


def test_both_fail_returns_generic_502_without_leak(transport):
    module, _, _ = transport
    _primary(transport).side_effect = OpenAIError('SYNTHETIC_PRIVATE_DETAIL')
    _fallback(transport).side_effect = OpenAIError('ANOTHER_PRIVATE_DETAIL')
    with pytest.raises(HTTPException) as failure:
        module.chat('S', 'U')
    assert failure.value.status_code == 502
    assert 'PRIVATE_DETAIL' not in failure.value.detail
    assert '.invalid' not in failure.value.detail


def test_both_timeout_returns_504(transport):
    module, _, _ = transport
    _primary(transport).side_effect = APITimeoutError(request=object())
    _fallback(transport).side_effect = APITimeoutError(request=object())
    with pytest.raises(HTTPException) as failure:
        module.chat('S', 'U')
    assert failure.value.status_code == 504


def test_blank_fallback_base_url_reuses_primary_client(transport, monkeypatch):
    module, factory, _ = transport
    monkeypatch.setattr(settings, 'LLM_FALLBACK_BASE_URL', '', raising=False)
    _primary(transport).side_effect = [_ok(''), _ok('FALLBACK_VIA_SAME_BASE')]
    assert module.chat('S', 'U') == 'FALLBACK_VIA_SAME_BASE'
    assert factory.call_count == 1
    models = [call.kwargs['model'] for call in _primary(transport).call_args_list]
    assert models == ['primary-model', 'fallback-model']


@pytest.mark.parametrize('choices', [None, {}, [None], [SimpleNamespace(message=None)]])
def test_malformed_primary_response_uses_fallback(transport, choices):
    module, _, _ = transport
    _primary(transport).return_value = SimpleNamespace(choices=choices)
    _fallback(transport).return_value = _ok('FALLBACK_OK')
    assert module.chat('S', 'U') == 'FALLBACK_OK'
    assert _fallback(transport).call_count == 1


def test_both_malformed_responses_return_safe_502(transport):
    module, _, _ = transport
    _primary(transport).return_value = SimpleNamespace(choices=None)
    _fallback(transport).return_value = SimpleNamespace(choices=None)
    with pytest.raises(HTTPException) as failure:
        module.chat('S', 'U')
    assert failure.value.status_code == 502
    assert _fallback(transport).call_count == 1


def test_each_result_retains_its_own_model(transport):
    module, _, _ = transport
    _primary(transport).side_effect = [OpenAIError('SYNTHETIC_FAILURE'), _ok('PRIMARY_OK')]
    _fallback(transport).return_value = _ok('FALLBACK_OK')
    fallback = module.chat_with_model('S', 'U')
    primary = module.chat_with_model('S', 'U')
    assert (fallback.content, fallback.model_used) == ('FALLBACK_OK', 'fallback-model')
    assert (primary.content, primary.model_used) == ('PRIMARY_OK', 'primary-model')
