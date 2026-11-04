"""LLM client interface + structured-output helper with the self-correction loop.

Hardened (Oct 28 audit): transport/rate-limit errors from the provider are retried here so
the callers' deterministic fallbacks actually engage instead of failing the run; the schema
instruction is merged into the FIRST system message (many open models reject a second
system message after user content); and reasoning-model `<think>` blocks plus markdown
fences are stripped before JSON extraction.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.schemas import Usage

T = TypeVar("T", bound=BaseModel)

THINK_BLOCK = re.compile(r"<think>[\s\S]*?</think>", re.I)
CODE_FENCE = re.compile(r"```[a-zA-Z]*")


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


class LLMClient(Protocol):
    name: str

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> LLMResponse: ...


class StructuredOutputError(Exception):
    pass


def extract_json(text: str) -> dict:
    cleaned = THINK_BLOCK.sub("", text)
    cleaned = CODE_FENCE.sub("", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in reply")
    return json.loads(cleaned[start : end + 1])


def _with_schema_instruction(messages: list[dict], schema: type[BaseModel]) -> list[dict]:
    """One system message, first: the schema instruction rides along with the rules.
    A second system message after user content is rejected by many open-model servers."""
    instruction = (
        f"\nReply with exactly ONE JSON object matching this schema:\n{schema.model_json_schema()}"
    )
    msgs = [dict(m) for m in messages]
    if msgs and msgs[0].get("role") == "system":
        msgs[0]["content"] = str(msgs[0].get("content", "")) + instruction
    else:
        msgs = [{"role": "system", "content": instruction.strip()}] + msgs
    return msgs


async def structured(
    client: LLMClient,
    messages: list[dict],
    *,
    model: str,
    schema: type[T],
    usage: Usage | None = None,
    retries: int = 2,
) -> T:
    """Ask for one JSON object matching the schema. Invalid output OR transport errors
    (timeout, 429, 5xx) are retried; the caller's deterministic fallback takes over after."""
    msgs = _with_schema_instruction(messages, schema)
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = await client.chat(msgs, model=model, json_mode=True)
        except Exception as e:  # noqa: BLE001 — transport failures are retryable, then fallback
            last_err = e
            await asyncio.sleep(min(2**attempt * 0.25, 1.0))
            continue
        if usage is not None:
            usage.add(resp.prompt_tokens, resp.completion_tokens)
        try:
            return schema.model_validate(extract_json(resp.content))
        except (ValueError, ValidationError, json.JSONDecodeError) as e:
            last_err = e
            msgs = msgs + [
                {"role": "assistant", "content": resp.content},
                {
                    "role": "user",
                    "content": f"Your JSON was invalid: {e}. Return corrected JSON only.",
                },
            ]
    raise StructuredOutputError(f"{schema.__name__} after retries: {last_err}")
