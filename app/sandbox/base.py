"""Sandbox interfaces. One run creates two sessions (base branch, PR head) from the same
backend; PR code only ever runs inside these sessions, never in the app process."""
from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

Phase = Literal["install", "tests"]


class RepoSpec(BaseModel):
    url: str
    owner: str
    repo: str
    number: int
    ref: Literal["base", "pr"]


class ExecResult(BaseModel):
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class BehaviourReport(BaseModel):
    """What the sandbox observed. Populated by the backend."""

    network_attempts: list[str] = Field(default_factory=list)
    proxy_denied: list[str] = Field(default_factory=list)
    canary_hits: list[str] = Field(default_factory=list)
    fs_denied: list[str] = Field(default_factory=list)
    limits_hit: list[str] = Field(default_factory=list)


class SandboxSession(Protocol):
    which: Literal["base", "pr"]

    async def exec(self, command: str, *, phase: Phase, timeout_s: int) -> ExecResult: ...

    async def write_file(self, path: str, content: str) -> None: ...

    async def materialize(self, tarball: bytes) -> None:
        """Unpack a repo tarball into the workspace (real backends; dummy no-op)."""
        ...

    async def use_network(self, enable: bool) -> None:
        """Default-deny: attach the registry-only egress network for install, none for tests."""
        ...

    async def behaviour(self) -> BehaviourReport: ...

    async def destroy(self) -> None: ...


class SandboxBackend(Protocol):
    name: str

    async def create(
        self, spec: RepoSpec, *, language: str, run_id: str, canaries: dict[str, str]
    ) -> SandboxSession: ...


def make_canaries() -> dict[str, str]:
    """Planted fake keys, randomized per run (fixed doc-example keys are
    trivially skip-listed by careful malware). Formats still match the secret-shape
    regexes so redaction and detection keep working. Real keys never enter a sandbox."""
    import secrets
    import string

    upper = string.ascii_uppercase + string.digits
    alnum = string.ascii_letters + string.digits
    return {
        "AWS_ACCESS_KEY_ID": "AKIA" + "".join(secrets.choice(upper) for _ in range(16)),
        "GITHUB_TOKEN": "ghp_" + "".join(secrets.choice(alnum) for _ in range(36)),
        "OPENAI_API_KEY": "sk-canary-" + secrets.token_urlsafe(24),
    }
