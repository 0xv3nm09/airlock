"""Pydantic contracts shared by API, agents, store and tests. Enum values are part of the
data contract (workbook: Data contracts) — never rename once the UI uses them."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class VerdictLabel(str, Enum):
    safe_to_merge = "safe_to_merge"
    needs_changes = "needs_changes"
    suspicious = "suspicious"
    inconclusive = "inconclusive"


class Route(str, Enum):
    auto = "auto"
    human_review = "human_review"


class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class FindingCategory(str, Enum):
    known_malicious_dependency = "known_malicious_dependency"
    young_package = "young_package"
    prompt_injection = "prompt_injection"
    network_attempt = "network_attempt"
    secret_access = "secret_access"
    fs_escape_attempt = "fs_escape_attempt"
    resource_abuse = "resource_abuse"
    test_regression = "test_regression"
    bug_proven = "bug_proven"
    setup_failure = "setup_failure"


class Dep(BaseModel):
    ecosystem: Literal["PyPI", "npm"]
    name: str
    version: str | None = None
    is_new: bool = False


class PRFile(BaseModel):
    path: str
    patch: str = ""


class PRInfo(BaseModel):
    url: str
    owner: str
    repo: str
    number: int
    title: str = ""
    body: str = ""
    language: Literal["python", "node"] = "python"
    base_ref: str = "main"
    files: list[PRFile] = Field(default_factory=list)
    deps: list[Dep] = Field(default_factory=list)
    scenario: str | None = None  # dummy mode only

    @property
    def diff_text(self) -> str:
        return "\n\n".join(f"--- a/{f.path}\n{f.patch}" for f in self.files)


class Evidence(BaseModel):
    kind: str  # behaviour | exec | advisory | pattern
    step_id: str | None = None
    excerpt: str = ""
    command: str | None = None
    exit_code: int | None = None


class Finding(BaseModel):
    id: str = ""  # assigned by the repository as F1, F2, ...
    category: FindingCategory
    severity: Severity
    title: str
    proven: bool = False
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)


class Verdict(BaseModel):
    label: VerdictLabel
    confidence: float
    route: Route
    summary: str = ""
    reasons: list[str] = Field(default_factory=list)
    cited_findings: list[str] = Field(default_factory=list)


class ContainmentCounters(BaseModel):
    network_blocked: int = 0
    canary_hits: int = 0
    writes_denied: int = 0
    limits_hit: int = 0


class IntentAssessment(BaseModel):
    """Security Analyst output — explains intent; never changes the verdict."""

    intent: Literal["benign", "data_theft", "backdoor", "sabotage", "cryptomining", "unclear"]
    explanation: str = Field(max_length=600)
    cited_evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, default=0.0)


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_calls: int = 0

    def add(self, prompt: int, completion: int) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.llm_calls += 1

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class Event(BaseModel):
    run_id: str
    seq: int
    ts: datetime
    type: str
    name: str
    data: dict[str, Any] = Field(default_factory=dict)


class RunCreate(BaseModel):
    pr_url: str


class DemoRunCreate(BaseModel):
    scenario: Literal["clean", "buggy", "malicious"]


class RunOut(BaseModel):
    id: str
    owner_id: str
    is_demo: bool = False
    status: RunStatus
    pr_url: str
    policy_version: str
    verdict: Verdict | None = None
    intent: IntentAssessment | None = None
    findings: list[Finding] = Field(default_factory=list)
    counters: ContainmentCounters = Field(default_factory=ContainmentCounters)
    usage: Usage = Field(default_factory=Usage)
    error: str | None = None
    human_decision: Literal["approved", "rejected"] | None = None
    human_note: str = ""
    decided_by: str | None = None
    decided_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


class DecisionCreate(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=1000)


class SessionCreate(BaseModel):
    api_key: str = Field(min_length=8, max_length=200)


class ApiKeyCreate(BaseModel):
    owner_id: str = Field(min_length=2, max_length=60, pattern=r"^[\w.\- ]+$")
    scopes: list[Literal["runs:read", "runs:write", "runs:approve"]] = Field(
        default=["runs:read", "runs:write"], max_length=3
    )


class ApiKeyOut(BaseModel):
    key_id: str
    key: str  # the full secret — returned ONCE, never stored in plaintext
    owner_id: str
    scopes: list[str]
    revoked: bool = False


class ApiKeyInfo(BaseModel):
    key_id: str
    owner_id: str
    scopes: list[str]
    revoked: bool
    created_at: str
