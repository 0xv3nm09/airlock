"""Composition: pick the LLM client from settings."""
from __future__ import annotations

from app.core.config import Settings
from app.llm.base import LLMClient
from app.llm.dummy import DummyLLM
from app.llm.vultr import VultrLLM


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "vultr":
        if not settings.vultr_inference_api_key.get_secret_value():
            raise RuntimeError("AIRLOCK_VULTR_INFERENCE_API_KEY is required for llm_provider=vultr")
        return VultrLLM(settings)
    return DummyLLM()
