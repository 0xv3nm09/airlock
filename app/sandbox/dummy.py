"""Dummy sandbox backend: scripted, scenario-driven sessions. Lets the full pipeline run
offline (dev, CI, demo replay) and makes the behaviour scan's findings deterministic."""
from __future__ import annotations

import asyncio
from typing import Literal

from app.sandbox.base import BehaviourReport, ExecResult, Phase, RepoSpec
from app.sources.dummy import Scenario, scenario_for


class DummySandboxSession:
    def __init__(self, which: Literal["base", "pr"], sc: Scenario, canaries: dict[str, str], on_destroy):
        self.which = which
        self._sc = sc
        self._canaries = canaries
        self._on_destroy = on_destroy
        self._outputs: list[ExecResult] = []
        self._install_attempts = 0
        self._destroyed = False

    async def exec(self, command: str, *, phase: Phase, timeout_s: int) -> ExecResult:
        await asyncio.sleep(0.005)
        sc = self._sc
        is_pr = self.which == "pr"
        res = ExecResult(duration_ms=250)

        if phase == "install":
            if command.startswith("python -m venv"):
                res.stdout = "venv created"  # fixed setup step; not a scripted attempt
                return res
            if is_pr:
                self._install_attempts += 1
            if is_pr and sc.setup_fail_always:
                res.exit_code = 1
                res.stderr = (
                    "ERROR: Could not find a version that satisfies the requirement "
                    "no-such-package-anywhere==9.9.9 (from versions: none)"
                )
                res.duration_ms = 120
            elif is_pr and sc.setup_fail_first and self._install_attempts == 1:
                res.exit_code = 1
                res.stderr = (
                    "ERROR: Could not open requirements file: "
                    "requirements-wrong.txt: No such file or directory"
                )
                res.duration_ms = 120
            elif is_pr and sc.install_network_host:
                key = self._canaries["AWS_ACCESS_KEY_ID"] if sc.canary_hit else "x"
                res.stdout = (
                    "installing dependencies...\n"
                    f"postinstall: http://{sc.install_network_host}/upload?key={key}\n"
                    f"curl: (6) Could not resolve host: {sc.install_network_host}"
                )
                res.duration_ms = 900
            else:
                res.stdout = "dependencies installed"
        elif phase == "tests":
            if "test_airlock_generated" in command:
                if is_pr and sc.generated_fails_pr:
                    res.exit_code = 1
                    res.stderr = (
                        "FAILED tests/test_airlock_generated.py::test_generated_edge_case "
                        "- AssertionError: empty input crashed"
                    )
                else:
                    res.stdout = "1 passed"
            elif is_pr:
                if sc.limit == "time":
                    res.exit_code = 124
                    res.timed_out = True
                    res.stderr = "Timeout: the command exceeded the time limit"
                    res.duration_ms = timeout_s * 1000
                elif sc.limit == "memory":
                    res.exit_code = 137
                    res.stderr = "Killed (OOM): memory limit exceeded"
                elif sc.limit == "pids":
                    res.exit_code = 137
                    res.stderr = "fork loop detected: pids limit reached"
                elif not sc.tests_pass_pr:
                    res.exit_code = 1
                    res.stderr = f"1 failed: {sc.failing_test}"
                else:
                    res.stdout = "12 passed"
            else:
                res.stdout = "12 passed"
            if not is_pr and sc.base_tests_fail:
                res.exit_code = 1
                res.stderr = "FAILED tests/test_core.py::test_core - baseline is broken"

        if is_pr and sc.rm_rf_denied and phase == "tests":
            # The scripted test run includes the destructive call; the read-only root denies it.
            sep = "\n" if res.stderr else ""
            res.stderr = res.stderr + sep + "rm: cannot remove '/usr': Read-only file system"
        if is_pr and sc.test_network_host and phase == "tests" and "test_airlock_generated" not in command:
            res.stderr += (
                f"\nConnectionError: could not connect to {sc.test_network_host}"
            )

        self._outputs.append(res)
        return res

    async def write_file(self, path: str, content: str) -> None:
        await asyncio.sleep(0)

    async def materialize(self, tarball: bytes) -> None:
        await asyncio.sleep(0)  # dummy scenarios are pre-seeded; nothing to unpack

    async def use_network(self, enable: bool) -> None:
        await asyncio.sleep(0)  # scripted scenarios simulate egress themselves

    async def behaviour(self) -> BehaviourReport:
        sc = self._sc
        if self.which != "pr":
            return BehaviourReport()
        raw = "\n".join((r.stdout or "") + (r.stderr or "") for r in self._outputs)
        canaries_seen = [name for name, v in self._canaries.items() if v and v in raw]
        fs_denied = []
        if "Read-only file system" in raw:
            fs_denied.append("write outside the repo denied (read-only root)")
        limits = [sc.limit] if sc.limit else []
        network = []
        if sc.install_network_host:
            network.append(sc.install_network_host)
        if sc.test_network_host:
            network.append(sc.test_network_host)
        return BehaviourReport(
            network_attempts=network,
            proxy_denied=[f"DENIED {h}" for h in network],
            canary_hits=canaries_seen,
            fs_denied=fs_denied,
            limits_hit=limits,
        )

    async def destroy(self) -> None:
        if not self._destroyed:
            self._destroyed = True
            self._on_destroy()


class DummySandbox:
    name = "dummy"
    created = 0
    alive = 0  # class counters double as test assertions for lifecycle discipline

    async def create(
        self, spec: RepoSpec, *, language: str, run_id: str, canaries: dict[str, str]
    ) -> DummySandboxSession:
        sc = scenario_for(spec.owner, spec.repo)
        DummySandbox.created += 1
        DummySandbox.alive += 1

        def _dec() -> None:
            DummySandbox.alive -= 1

        return DummySandboxSession(spec.ref, sc, canaries, _dec)
