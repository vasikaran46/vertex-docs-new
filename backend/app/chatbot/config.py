import os
import re
from typing import Any


def get_llm_config() -> dict[str, Any]:
    """
    Centralized configuration for LLM provider, base URL, API key, model, and temperature.
    Supports OpenRouter, Groq, Gemini, and generic OpenAI-compatible providers.
    Reads from environment variables with sensible defaults.
    Never exposes or logs raw keys.
    """
    # 1. API Key resolution (check specific keys first, then fallback to LLM_API_KEY)
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    generic_key = os.getenv("LLM_API_KEY", "").strip()

    # 2. Base URL & Provider detection
    configured_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    configured_base = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    configured_model = os.getenv("LLM_MODEL", "").strip()

    key = ""
    provider = "openrouter"
    base_url = "https://openrouter.ai/api/v1"
    model = "openai/gpt-4o-mini"

    if configured_provider == "groq" or (not configured_provider and (groq_key or "groq.com" in configured_base)):
        provider = "groq"
        key = groq_key or generic_key
        base_url = configured_base or "https://api.groq.com/openai/v1"
        model = configured_model or "llama-3.3-70b-versatile"
    elif configured_provider == "gemini" or (not configured_provider and (gemini_key or "googleapis.com" in configured_base)):
        provider = "gemini"
        key = gemini_key or generic_key
        base_url = configured_base or "https://generativelanguage.googleapis.com/v1beta/openai"
        model = configured_model or "gemini-2.0-flash"
    elif configured_provider == "openrouter" or (not configured_provider and (openrouter_key or generic_key.startswith("sk-or-") or "openrouter.ai" in configured_base)):
        provider = "openrouter"
        key = openrouter_key or generic_key
        base_url = configured_base or "https://openrouter.ai/api/v1"
        model = configured_model or "openai/gpt-4o-mini"
    else:
        # Generic or OpenAI
        provider = configured_provider or "openai"
        key = generic_key or openrouter_key or groq_key or gemini_key
        base_url = configured_base or "https://api.openai.com/v1"
        model = configured_model or "gpt-4o-mini"

    # Temperature
    try:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    except (ValueError, TypeError):
        temperature = 0.3

    # Timeout
    try:
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    except (ValueError, TypeError):
        timeout = 60.0

    return {
        "provider": provider,
        "key": key,
        "base_url": base_url,
        "model": model,
        "temperature": temperature,
        "timeout": timeout,
        "is_configured": bool(key),
    }


def get_fallback_models(primary_model: str, provider: str) -> list[str]:
    """
    Returns an ordered list of fallback models for the given provider.
    """
    models = [primary_model]
    if provider == "openrouter":
        fallbacks = [
            "openai/gpt-4o-mini",
            "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.3-70b-instruct",
            "meta-llama/llama-3.1-8b-instruct:free",
        ]
        for f in fallbacks:
            if f not in models:
                models.append(f)
    elif provider == "groq":
        fallbacks = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ]
        for f in fallbacks:
            if f not in models:
                models.append(f)
    elif provider == "gemini":
        fallbacks = [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]
        for f in fallbacks:
            if f not in models:
                models.append(f)
    return models
