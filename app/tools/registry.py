"""Tool registry with per-agent allow-lists.
A model's tool call is untrusted input: four gates before anything executes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel

from app.core.errors import NotFound, ToolForbidden, ValidationFailed
from app.guardrails.output import check_command
from app.guardrails.policy import Policy
from app.sandbox.base import ExecResult, SandboxSession


class RunCommandIn(BaseModel):
    command: str
    phase: Literal["install", "tests"] = "tests"
    timeout_s: int | None = None


class WriteTestFileIn(BaseModel):
    path: str
    content: str


@dataclass
class ToolContext:
    session: SandboxSession
    policy: Policy
    run_id: str
    canaries: dict[str, str] = field(default_factory=dict)


Handler = Callable[[Any, ToolContext], Awaitable[Any]]


@dataclass
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    side_effect: str
    allowed_agents: frozenset[str]
    handler: Handler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    async def call(self, agent: str, name: str, args: dict, ctx: ToolContext) -> Any:
        tool = self._tools.get(name)  # gate 1: registered?
        if tool is None:
            raise NotFound(f"tool {name} is not registered")
        if agent not in tool.allowed_agents:  # gate 2: permission?
            raise ToolForbidden(f"agent {agent} may not call {name}")
        try:
            parsed = tool.input_model.model_validate(args)  # gate 3: args valid? -> retryable
        except Exception as e:
            raise ValidationFailed(f"invalid args for {name}: {e}") from e
        return await tool.handler(parsed, ctx)  # gate 4 lives inside the handler


async def _run_command(args: RunCommandIn, ctx: ToolContext) -> ExecResult:
    check_command(args.command, ctx.policy)  # gate 4: policy
    timeout = args.timeout_s or (
        ctx.policy.install_timeout_s if args.phase == "install" else ctx.policy.test_timeout_s
    )
    result = await ctx.session.exec(args.command, phase=args.phase, timeout_s=timeout)
    from app.guardrails.output import redact_with_canaries

    return result.model_copy(
        update={
            "stdout": redact_with_canaries(result.stdout, ctx.canaries),
            "stderr": redact_with_canaries(result.stderr, ctx.canaries),
        }
    )


async def _write_test_file(args: WriteTestFileIn, ctx: ToolContext) -> dict:
    if not args.path.startswith("tests/") or ".." in args.path:
        from app.core.errors import PolicyViolation

        raise PolicyViolation("generated tests must live under tests/")
    if len(args.content) > ctx.policy.max_generated_chars:
        from app.core.errors import PolicyViolation

        raise PolicyViolation("generated test exceeds the size limit")
    await ctx.session.write_file(args.path, args.content)
    return {"written": args.path}


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        Tool(
            name="run_command",
            description="Run an allow-listed command in this run's sandbox",
            input_model=RunCommandIn,
            side_effect="execute",
            allowed_agents=frozenset({"runner", "fixer"}),
            handler=_run_command,
        )
    )
    reg.register(
        Tool(
            name="write_test_file",
            description="Write one generated test under tests/",
            input_model=WriteTestFileIn,
            side_effect="write",
            allowed_agents=frozenset({"test_writer"}),
            handler=_write_test_file,
        )
    )
    return reg
