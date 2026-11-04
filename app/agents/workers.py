"""Fixer, Test-writer, Security Analyst and Reporter agents. Small schemas; the Fixer is
the only looping agent (max 2 retries); the Analyst never changes the verdict."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.agents.prompts import (
    analyst_task,
    fence,
    fixer_task,
    reporter_task,
    shared_prefix,
    test_writer_task,
)
from app.core.events import RunTrace
from app.llm.base import StructuredOutputError, structured
from app.schemas import Finding, IntentAssessment, Usage
from app.services import Services


class CommandFix(BaseModel):
    command: str
    explanation: str = ""


class GeneratedTest(BaseModel):
    path: str = "tests/test_airlock_generated.py"
    code: str = Field(max_length=6000)


class Report(BaseModel):
    summary: str = Field(max_length=1200)


def _messages(svc: Services, role_prompt: str, payload_json: str) -> list[dict]:
    return [
        {"role": "system", "content": shared_prefix(svc.policy.version) + role_prompt},
        {"role": "user", "content": payload_json},
    ]


async def run_fixer(
    svc: Services, command: str, stderr_tail: str, language: str, trace: RunTrace, usage: Usage
) -> CommandFix:
    await trace.span_start("agent.fixer")
    import json

    payload = json.dumps(
        {
            "command": command,
            "stderr_tail": stderr_tail[-800:],
            "allowed_commands": svc.policy.allowed_commands(language),
        }
    )
    try:
        fix = await structured(
            svc.llm,
            _messages(svc, fixer_task(), payload),
            model=svc.settings.coder_model or "coder",
            schema=CommandFix,
            usage=usage,
        )
    except StructuredOutputError:
        fix = CommandFix(command=command, explanation="fixer unavailable; retrying original")
    await trace.span_end("agent.fixer", command=fix.command[:120])
    return fix


async def run_test_writer(
    svc: Services,
    target: str,
    hypothesis: str,
    language: str,
    trace: RunTrace,
    usage: Usage,
    target_patch: str = "",
) -> GeneratedTest | None:
    await trace.span_start("agent.test_writer")
    import json

    payload = json.dumps(
        {
            "target": target,
            "hypothesis": hypothesis,
            "framework": "pytest" if language == "python" else "jest",
            "target_patch": fence("TARGET_PATCH", target_patch[:4000]) if target_patch else "",
        }
    )
    try:
        test = await structured(
            svc.llm,
            _messages(svc, test_writer_task(), payload),
            model=svc.settings.coder_model or "coder",
            schema=GeneratedTest,
            usage=usage,
        )
    except StructuredOutputError:
        await trace.span_end("agent.test_writer", error="structured output failed")
        return None
    await trace.span_end("agent.test_writer", target=target, path=test.path)
    return test


async def run_analyst(
    svc: Services, findings: list[Finding], signals: list[str], trace: RunTrace, usage: Usage
) -> IntentAssessment | None:
    await trace.span_start("agent.analyst")
    import json

    payload = json.dumps(
        {
            "findings": [
                {"id": f.id, "category": f.category.value, "title": f.title, "confidence": f.confidence}
                for f in findings
            ],
            "static_signals": signals[:8],
        }
    )
    try:
        intent = await structured(
            svc.llm,
            _messages(svc, analyst_task(), payload),
            model=svc.settings.planner_model or "planner",
            schema=IntentAssessment,
            usage=usage,
        )
    except StructuredOutputError:
        await trace.span_end("agent.analyst", error="structured output failed")
        return None
    await trace.span_end("agent.analyst", intent=intent.intent)
    return intent


async def run_reporter(
    svc: Services, verdict_payload: dict, findings: list[Finding], trace: RunTrace, usage: Usage
) -> str:
    await trace.span_start("agent.reporter")
    import json

    payload = json.dumps(
        {
            "verdict": verdict_payload,
            "findings": [{"id": f.id, "title": f.title, "severity": f.severity.value} for f in findings],
        }
    )
    summary: str | None = None
    try:
        report = await structured(
            svc.llm,
            _messages(svc, reporter_task(), payload),
            model=svc.settings.planner_model or "planner",
            schema=Report,
            usage=usage,
        )
        cited = set(re.findall(r"\[(F\d+)\]", report.summary))
        valid_ids = {f.id for f in findings}
        if findings and (not cited or not cited.issubset(valid_ids)):
            summary = None  # unfaithful: fall back to the template
        else:
            summary = report.summary
    except StructuredOutputError:
        summary = None
    if summary is None:
        parts = " ".join(f"[{f.id}] {f.title}." for f in findings)
        label = verdict_payload.get("label", "unknown")
        summary = f"Verdict {label}. " + (parts if parts else "No findings.")
    await trace.span_end("agent.reporter", model=svc.llm.name)
    return summary
