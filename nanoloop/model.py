"""OpenRouter model factory.

OpenRouter exposes an OpenAI-compatible API, so we use langchain_openai.ChatOpenAI
with a custom base_url. DeepAgents accepts any LangChain chat model object.
"""
from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def make_model(model: str | None = None, *, temperature: float = 0.0) -> ChatOpenAI:
    """Build a ChatOpenAI pointed at OpenRouter.

    model: OpenRouter slug, e.g. "anthropic/claude-opus-4.8". Falls back to
    HARNESS_MODEL env var.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set (see .env.example)")

    slug = model or os.environ.get("HARNESS_MODEL", "openrouter/owl-alpha")

    # OpenRouter ranking/attribution headers (optional).
    headers = {}
    if site := os.environ.get("OPENROUTER_SITE_URL"):
        headers["HTTP-Referer"] = site
    if app := os.environ.get("OPENROUTER_APP_NAME"):
        headers["X-Title"] = app

    # Cap output tokens — OpenRouter charges by reserved max_tokens and bills 402
    # if balance can't cover it. DeepAgents otherwise requests 65536.
    max_tokens = int(os.environ.get("HARNESS_MAX_TOKENS", "4096"))

    # Retry transient upstream errors (OpenRouter 429/5xx, e.g. flaky alpha models).
    max_retries = int(os.environ.get("HARNESS_MAX_RETRIES", "5"))

    # Native OpenRouter gateway fallback: pass `models` array via extra_body and
    # let OpenRouter route through the list server-side. Keeps a single
    # BaseChatModel so DeepAgents' resolve_model accepts it (LangChain-level
    # with_fallbacks returns a RunnableWithFallbacks, which DeepAgents rejects).
    extra_body = {}
    fbs = os.environ.get("HARNESS_FALLBACK_MODEL", "")
    chain = [s.strip() for s in fbs.split(",") if s.strip() and s.strip() != slug]
    if chain:
        extra_body = {"models": [slug, *chain], "route": "fallback"}

    return ChatOpenAI(
        model=slug,
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        default_headers=headers or None,
        extra_body=extra_body or None,
    )


def subagent_model() -> ChatOpenAI:
    """Cheaper model for role subagents; falls back to main model."""
    slug = os.environ.get("HARNESS_SUBAGENT_MODEL")
    return make_model(slug)
