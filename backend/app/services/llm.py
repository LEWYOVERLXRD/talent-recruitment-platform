"""大模型调用封装：通过 OpenAI 兼容接口调用阿里云百炼的千问 qwen。

复用实验中「load_dotenv → OpenAI 客户端 → chat.completions.create → 取 content」的调用链，
只是把配置统一收口到 app/core/config.py 的 LLM_* 字段。
"""
from openai import OpenAI
from fastapi import HTTPException

from app.core.config import settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """惰性创建 OpenAI 兼容客户端（单例，避免重复初始化）"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _client


def chat(system_prompt: str, user_prompt: str) -> str:
    """调用大模型，返回回复正文文本"""
    if not settings.LLM_API_KEY or not settings.LLM_BASE_URL:
        raise HTTPException(503, "尚未配置大模型服务")
    from openai import APITimeoutError, OpenAIError
    try:
        client = get_client()
        resp = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise HTTPException(502, "大模型返回内容为空或格式异常，请稍后重试")
        return content
    except APITimeoutError:
        raise HTTPException(504, "大模型请求超时，请稍后重试") from None
    except (OpenAIError, IndexError, AttributeError):
        raise HTTPException(502, "大模型服务异常，请稍后重试") from None
