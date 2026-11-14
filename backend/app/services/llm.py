"""大模型调用封装：通过 OpenAI 兼容接口调用阿里云百炼的千问 qwen。

复用实验中「load_dotenv → OpenAI 客户端 → chat.completions.create → 取 content」的调用链，
只是把配置统一收口到 app/core/config.py 的 LLM_* 字段。

主模型不可用时自动降级到备用模型（若配置 LLM_FALLBACK_MODEL），
全部候选失败才返回错误，并在日志中记录本次实际使用的模型。
"""
import logging
from dataclasses import dataclass
from openai import OpenAI
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

_clients: dict[str, OpenAI] = {}


@dataclass(frozen=True)
class ChatResult:
    content: str
    model_used: str


def get_client(base_url: str = "") -> OpenAI:
    """惰性创建 OpenAI 兼容客户端（按 base_url 缓存，避免重复初始化）"""
    base_url = base_url or settings.LLM_BASE_URL
    if base_url not in _clients:
        _clients[base_url] = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=base_url,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _clients[base_url]


def _candidates() -> list[tuple[str, str]]:
    """按优先级返回 (model, base_url) 候选：主模型在前，备用模型在后

    备用字段用 getattr 读取，兼容测试环境的轻量配置替身。
    """
    candidates = [(settings.LLM_MODEL, settings.LLM_BASE_URL)]
    fallback_model = getattr(settings, 'LLM_FALLBACK_MODEL', '')
    if fallback_model:
        fallback_base = getattr(settings, 'LLM_FALLBACK_BASE_URL', '') or settings.LLM_BASE_URL
        candidates.append((fallback_model, fallback_base))
    return candidates


def _create(model: str, base_url: str, system_prompt: str, user_prompt: str) -> str:
    """调用指定模型，返回回复正文；内容为空或格式异常时抛 ValueError"""
    client = get_client(base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    choices = getattr(resp, 'choices', None)
    if not isinstance(choices, list) or not choices:
        raise ValueError("invalid completion choices")
    content = getattr(getattr(choices[0], 'message', None), 'content', None)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("empty completion content")
    return content


def chat(system_prompt: str, user_prompt: str) -> str:
    """兼容只需要回复正文的调用方。"""
    return chat_with_model(system_prompt, user_prompt).content


def chat_with_model(system_prompt: str, user_prompt: str) -> ChatResult:
    """返回回复正文及实际使用的模型；主模型失败时尝试备用模型。"""
    if not settings.LLM_API_KEY or not settings.LLM_BASE_URL:
        raise HTTPException(503, "尚未配置大模型服务")
    from openai import APITimeoutError, OpenAIError

    last_error: HTTPException | None = None
    for index, (model, base_url) in enumerate(_candidates()):
        try:
            content = _create(model, base_url, system_prompt, user_prompt)
        except APITimeoutError:
            last_error = HTTPException(504, "大模型请求超时，请稍后重试")
        except (OpenAIError, IndexError, AttributeError):
            last_error = HTTPException(502, "大模型服务异常，请稍后重试")
        except ValueError:
            last_error = HTTPException(502, "大模型返回内容为空或格式异常，请稍后重试")
        else:
            if index > 0:
                logger.warning("主模型不可用，已降级使用备用模型 %s", model)
            logger.info("LLM 调用完成，本次使用模型 %s", model)
            return ChatResult(content=content, model_used=model)
        logger.warning("模型 %s 调用失败，尝试下一个候选", model)
    raise last_error from None
