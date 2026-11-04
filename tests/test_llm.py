"""LLM layer: JSON extraction robustness, single system message, transport-error retries."""
import pytest
from pydantic import BaseModel

from app.llm.base import LLMResponse, StructuredOutputError, extract_json, structured
from app.schemas import Usage


class Box(BaseModel):
    a: int


def test_extract_json_strips_think_blocks():
    text = "<think>Let me reason… maybe {decoy}</think>Here it is: {\"a\": 1}"
    assert extract_json(text) == {"a": 1}


def test_extract_json_strips_fences():
    text = "```json\n{\"a\": 2}\n```"
    assert extract_json(text) == {"a": 2}


def test_extract_json_no_object_raises():
    with pytest.raises(ValueError):
        extract_json("no json here")


class FlakyClient:
    name = "flaky"

    def __init__(self, failures: int, content: str = '{"a": 1}'):
        self.failures = failures
        self.content = content
        self.calls = 0
        self.last_messages: list[dict] = []

    async def chat(self, messages, *, model, temperature=0.0, max_tokens=1500, json_mode=False):
        self.calls += 1
        self.last_messages = messages
        if self.calls <= self.failures:
            raise TimeoutError("provider timed out")
        return LLMResponse(content=self.content, model="m", prompt_tokens=10, completion_tokens=5)


@pytest.mark.asyncio
async def test_transport_error_is_retried_then_fallback_data_returned():
    client = FlakyClient(failures=1)
    box = await structured(
        client, [{"role": "system", "content": "rules"}, {"role": "user", "content": "payload"}],
        model="m", schema=Box, retries=2,
    )
    assert box.a == 1
    assert client.calls == 2


@pytest.mark.asyncio
async def test_persistent_transport_error_raises_structured_error():
    client = FlakyClient(failures=99)
    with pytest.raises(StructuredOutputError):
        await structured(client, [{"role": "system", "content": "rules"}], model="m", schema=Box)


@pytest.mark.asyncio
async def test_single_system_message_first():
    client = FlakyClient(failures=0, content='{"a": 3}')
    await structured(
        client,
        [{"role": "system", "content": "rules"}, {"role": "user", "content": "payload"}],
        model="m", schema=Box,
    )
    roles = [m["role"] for m in client.last_messages]
    assert roles == ["system", "user"], "schema instruction must ride the first system message"
    assert "a" in client.last_messages[0]["content"]  # schema present in system block


@pytest.mark.asyncio
async def test_invalid_json_feeds_error_back():
    class BadThenGood(FlakyClient):
        async def chat(self, messages, **kwargs):
            self.calls += 1
            self.last_messages = messages
            if self.calls == 1:
                return LLMResponse(content="oops", model="m")
            return LLMResponse(content='{"a": 9}', model="m")

    client = BadThenGood(failures=0)
    usage = Usage()
    box = await structured(client, [{"role": "system", "content": "r"}], model="m", schema=Box, usage=usage)
    assert box.a == 9
    assert usage.llm_calls == 2
    assert any(m["role"] == "assistant" for m in client.last_messages)
