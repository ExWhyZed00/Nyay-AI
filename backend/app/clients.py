"""OpenAI clients (embeddings + chat model). Created once and reused."""
from functools import lru_cache

from langchain_openai import ChatOpenAI
from openai import OpenAI

from app.config import get_settings


@lru_cache
def get_openai() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.openai_api_key, timeout=60.0, max_retries=3)


@lru_cache
def get_llm() -> ChatOpenAI:
    s = get_settings()
    kwargs: dict = {}
    temp = s.openai_temperature.strip().lower()
    if temp not in {"", "default", "none"}:
        kwargs["temperature"] = float(temp)
    if s.openai_reasoning_effort.strip():
        kwargs["reasoning_effort"] = s.openai_reasoning_effort.strip()
    return ChatOpenAI(
        model=s.openai_chat_model,
        api_key=s.openai_api_key,
        timeout=90,
        max_retries=2,
        **kwargs,
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Turn texts into vectors. Output order matches input order."""
    s = get_settings()
    resp = get_openai().embeddings.create(model=s.openai_embedding_model, input=texts)
    return [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
