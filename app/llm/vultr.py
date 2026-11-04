"""Vultr Serverless Inference adapter (OpenAI-compatible). The only production provider.

Verified Oct 27 2026: base URL https://api.vultrinference.com/v1, model list at
GET /v1/models (public), chat limits 120 req/min and 16 concurrent, per-token billing.
Model IDs are lowercase slugs — resolve from /v1/models, never hardcode.
"""
from __future__ import annotations

import time

import httpx
from openai import AsyncOpenAI

from app.core.config import Settings
from app.llm.base import LLMResponse


class VultrLLM:
    name = "vultr"

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.vultr_inference_base_url,
            api_key=settings.vultr_inference_api_key.get_secret_value(),
            timeout=60,
            max_retries=3,
        )

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> LLMResponse:
        t0 = time.monotonic()
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            r = await self._client.chat.completions.create(**kwargs)
        except Exception:  # noqa: BLE001 — some models reject response_format; retry plain
            if not json_mode:
                raise
            kwargs.pop("response_format", None)
            r = await self._client.chat.completions.create(**kwargs)
        usage = getattr(r, "usage", None)
        return LLMResponse(
            content=r.choices[0].message.content or "",
            model=str(getattr(r, "model", model)),
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    async def list_models(self) -> list[str]:
        """Live catalog from GET /v1/models (public, no auth needed)."""
        async with httpx.AsyncClient(
            base_url=self._settings.vultr_inference_base_url, timeout=15
        ) as client:
            r = await client.get("/models")
            r.raise_for_status()
            data = r.json()
        items = data.get("data") or data.get("models") or []
        ids = [m.get("id") if isinstance(m, dict) else str(m) for m in items]
        return [str(i) for i in ids if i]
