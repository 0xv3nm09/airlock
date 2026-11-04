"""Planner agent: fixed before any untrusted output is read (plan-then-execute)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.prompts import planner_payload, planner_task, shared_prefix
from app.core.errors import PolicyViolation
from app.core.events import RunTrace
from app.guardrails.output import check_command
from app.llm.base import StructuredOutputError, structured
from app.schemas import PRInfo, Usage
from app.services import Services


class Plan(BaseModel):
    language: str = "python"
    install_cmd: str = ""
    test_cmd: str = ""
    targets: list[str] = Field(default_factory=list, max_length=3)
    hypotheses: dict[str, str] = Field(default_factory=dict)


def fallback_plan(pr: PRInfo, ranked: list[tuple[str, list[str], int]]) -> Plan:
    if pr.language == "node":
        install, test = "npm ci", "npm test"
    else:
        install, test = "pip install -r requirements.txt", "python -m pytest -q"
    return Plan(
        language=pr.language,
        install_cmd=install,
        test_cmd=test,
        targets=[path for path, _, _ in ranked],
        hypotheses={path: "risk reasons: " + ", ".join(reasons) for path, reasons, _ in ranked},
    )


async def make_plan(
    svc: Services, pr: PRInfo, ranked: list[tuple[str, list[str], int]], trace: RunTrace, usage: Usage
) -> Plan:
    await trace.span_start("agent.planner")
    used_fallback = False
    try:
        msgs = [
            {
                "role": "system",
                "content": shared_prefix(svc.policy.version)
                + planner_task().format(language=pr.language),
            },
            {
                "role": "user",
                "content": planner_payload(
                    pr, ranked, svc.policy.allowed_commands(pr.language)
                ),
            },
        ]
        plan = await structured(
            svc.llm,
            msgs,
            model=svc.settings.planner_model or "planner",
            schema=Plan,
            usage=usage,
        )
        check_command(plan.install_cmd, svc.policy)
        check_command(plan.test_cmd, svc.policy)
    except (StructuredOutputError, PolicyViolation, ValueError):
        plan = fallback_plan(pr, ranked)
        used_fallback = True
    await trace.span_end(
        "agent.planner",
        model=svc.llm.name,
        fallback=used_fallback,
        targets=plan.targets,
        language=plan.language,
    )
    return plan
