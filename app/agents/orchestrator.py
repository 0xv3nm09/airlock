"""Code-owned review pipeline: screen → pre-flight → plan → detonate → prove → observe →
decide → clean up. The verdict comes from the rule table; the model only writes prose.
Every path destroys the sandboxes (finally), and a janitor catches crash leftovers."""
from __future__ import annotations

import asyncio
import logging
from typing import Literal

from app.agents.planner import make_plan
from app.agents.workers import run_analyst, run_fixer, run_reporter, run_test_writer
from app.core.errors import PolicyViolation
from app.core.events import RunTrace
from app.guardrails.input import scan_prompt_injection
from app.guardrails.output import check_command, redact
from app.preflight.osv import check_known_malicious, check_package_age
from app.preflight.static_scan import rank_files, scan_diff
from app.sandbox.base import RepoSpec, SandboxSession, make_canaries
from app.schemas import (
    ContainmentCounters,
    Evidence,
    Finding,
    FindingCategory,
    RunStatus,
    Severity,
    Usage,
    Verdict,
)
from app.scoring.verdict import BREAKING, DANGER, route_for, verdict_from_findings
from app.services import Services
from app.tools.registry import ToolContext, build_registry

log = logging.getLogger("airlock.orchestrator")


class RunCancelled(Exception):
    pass


async def execute_run(svc: Services, run_id: str, pr_url: str) -> None:
    orch = _Orchestrator(svc, run_id, pr_url)
    await orch.run()


class _Orchestrator:
    def __init__(self, svc: Services, run_id: str, pr_url: str):
        self.svc = svc
        self.run_id = run_id
        self.pr_url = pr_url
        self.trace = RunTrace(svc.repo, svc.bus, run_id)
        self.registry = build_registry()
        self.usage = Usage()
        self.counters = ContainmentCounters()
        self.sessions: list[SandboxSession] = []
        self.tests_ran = False
        self._install_ok = False
        self._limit_findings = 0
        self._exec_seq = 0
        self._destroy_emitted = False
        self.canaries: dict[str, str] = {}

    # ------------------------------------------------------------------ run
    async def run(self) -> None:
        svc, run_id = self.svc, self.run_id
        try:
            await self.trace.status("running")
            await svc.repo.set_status(run_id, RunStatus.running)

            pr = await self._fetch_pr()
            self._checkpoint()

            pre = await self._preflight(pr)
            findings = pre["findings"]
            ranked = pre["ranked"]
            signals = pre["signals"]

            if not pre["stop_run"]:
                plan = await make_plan(svc, pr, ranked, self.trace, self.usage)
                self._checkpoint()
                findings += await self._detonate(pr, plan)
            else:
                await self.trace.containment(
                    "preflight_stop", detail="known-malicious dependency; no sandbox created"
                )

            intent = None
            if self._analyst_warranted(findings, signals):
                intent = await run_analyst(svc, findings, signals, self.trace, self.usage)

            label, confidence, reasons = verdict_from_findings(findings, tests_ran=self.tests_ran)
            route = route_for(label, confidence, svc.policy)

            verdict_payload = {"label": label.value, "confidence": confidence, "route": route.value}
            summary = await run_reporter(svc, verdict_payload, findings, self.trace, self.usage)
            cited = [f.id for f in findings if f"[{f.id}]" in summary]

            verdict = Verdict(
                label=label,
                confidence=confidence,
                route=route,
                summary=summary,
                reasons=reasons,
                cited_findings=cited,
            )
            await svc.repo.set_verdict(run_id, verdict)
            await svc.repo.set_intent(run_id, intent)
            await svc.repo.set_counters(run_id, self.counters)
            await self._persist_usage()
            await svc.repo.set_status(run_id, RunStatus.completed, finished=True)
            await self.trace.verdict(verdict)
            await self.trace.status("completed")
        except RunCancelled:
            await self._persist_usage()
            await svc.repo.set_status(run_id, RunStatus.cancelled, finished=True)
            await self.trace.status("cancelled")
        except Exception as e:  # noqa: BLE001 — a run always ends in a clear status
            log.exception("run %s failed", run_id)
            await self._persist_usage()
            await svc.repo.set_status(run_id, RunStatus.failed, error=redact(str(e))[:300], finished=True)
            await self.trace.status("failed")
        finally:
            await self._destroy_all()

    # -------------------------------------------------------------- fetch
    async def _fetch_pr(self):
        await self.trace.span_start("github.fetch_pr")
        pr = await self.svc.pr_source.get_pr(self.pr_url)
        await self.trace.span_end("github.fetch_pr", language=pr.language, files=len(pr.files))
        return pr

    # ---------------------------------------------------------- preflight
    async def _preflight(self, pr) -> dict:
        findings: list[Finding] = []
        await self.trace.span_start("preflight.static")
        for rule, where, excerpt in scan_prompt_injection(pr.title, pr.body, pr.diff_text)[:1]:
            findings.append(
                await self._add_finding(
                    Finding(
                        category=FindingCategory.prompt_injection,
                        severity=Severity.high,
                        title=f"Prompt-injection pattern ({rule}) in PR {where}",
                        proven=False,
                        confidence=0.60,
                        evidence=[Evidence(kind="pattern", excerpt=excerpt[:200])],
                    )
                )
            )
        signals = [f"{s.path}: {s.reason} (+{s.score})" for s in scan_diff(pr)]
        ranked = rank_files(pr)
        await self.trace.span_end("preflight.static", signals=len(signals), ranked=ranked and [r[0] for r in ranked])

        await self.trace.span_start("preflight.osv")
        mal = await check_known_malicious(pr.deps, self.svc.osv)
        for f in mal:
            findings.append(await self._add_finding(f))
        young = await check_package_age(pr.deps, self.svc.age_lookup)
        for f in young:
            findings.append(await self._add_finding(f))
        await self.trace.span_end("preflight.osv", mal_hits=len(mal), young=len(young))

        return {
            "findings": findings,
            "signals": signals,
            "ranked": ranked,
            "stop_run": any(f.category is FindingCategory.known_malicious_dependency for f in findings),
        }

    # ------------------------------------------------------------ detonate
    async def _detonate(self, pr, plan) -> list[Finding]:
        svc = self.svc
        self.canaries = make_canaries()  # fresh, format-valid decoys per run
        await self.trace.span_start("sandbox.create")

        async def _create(ref: Literal["base", "pr"]) -> SandboxSession:
            spec = RepoSpec(url=pr.url, owner=pr.owner, repo=pr.repo, number=pr.number, ref=ref)
            session = await svc.sandbox.create(
                spec, language=plan.language, run_id=self.run_id, canaries=self.canaries
            )
            self.sessions.append(session)
            return session

        base_s, pr_s = await asyncio.gather(_create("base"), _create("pr"))
        await self.trace.span_end("sandbox.create", sandboxes=2, backend=getattr(svc.sandbox, "name", "unknown"))

        # Materialize the PR's code (real backends): base branch and PR head tarballs.
        # Dummy scenarios are pre-seeded and fetch_tarball returns empty there.
        refs = {"base": pr.base_ref, "pr": f"refs/pull/{pr.number}/head"}
        for session, ref_key in ((base_s, "base"), (pr_s, "pr")):
            tarball = await svc.pr_source.fetch_tarball(pr.owner, pr.repo, refs[ref_key])
            if tarball:
                await session.materialize(tarball)

        # Two-phase network: registry-only egress during install, none for tests.
        # Containers are created network-less; this attaches the proxy network temporarily.
        await asyncio.gather(base_s.use_network(True), pr_s.use_network(True))

        findings: list[Finding] = []
        try:
            findings += await self._install_all(base_s, pr_s, plan)
            await asyncio.gather(base_s.use_network(False), pr_s.use_network(False))
            self._checkpoint()
            if self._install_ok:
                findings += await self._run_tests(base_s, pr_s, plan)
                self._checkpoint()
                if self.tests_ran:
                    findings += await self._generated_tests(base_s, pr_s, plan, pr)
            else:
                # Install failed: tests would be meaningless — never a quiet "safe".
                self.tests_ran = False
                await self.trace.log(
                    "tests", tail="install failed; skipping tests so the run cannot read as safe"
                )
            # Findings are attributed to the PR sandbox, DIFFERENTIALLY: signals that the
            # baseline sandbox also produced (a repo whose own tests phone home) are
            # baseline behaviour, not the change's — logged, never blamed on the PR.
            base_report = await base_s.behaviour()
            await self._log_base_behaviour(base_s, base_report)
            findings += await self._observe([pr_s], baseline=base_report)
        finally:
            await self._destroy_all()
        return findings

    async def _install_all(self, base_s: SandboxSession, pr_s: SandboxSession, plan) -> list[Finding]:
        findings: list[Finding] = []
        all_installed = True
        for session in (base_s, pr_s):
            # Python deps must land inside a per-run venv on the writable workspace — the
            # root filesystem is read-only. The venv step is fixed policy, not planned.
            setup_cmd = (
                "python -m venv --system-site-packages /workspace/.venv"
                if plan.language == "python"
                else None
            )
            if setup_cmd:
                res = await self._exec(session, setup_cmd, "install")
                if not res.ok:
                    all_installed = False
                    findings.append(
                        await self._add_finding(
                            Finding(
                                category=FindingCategory.setup_failure,
                                severity=Severity.low,
                                title=f"Could not create the virtualenv on {session.which}",
                                proven=True,
                                confidence=0.90,
                                evidence=[
                                    Evidence(
                                        kind="exec",
                                        command=setup_cmd[:120],
                                        exit_code=res.exit_code,
                                        excerpt=res.stderr[:300],
                                    )
                                ],
                            )
                        )
                    )
                    continue
            command = plan.install_cmd
            installed = False
            for attempt in (1, 2, 3):
                res = await self._exec(session, command, "install")
                if res.ok:
                    installed = True
                    break
                if attempt < 3:
                    fix = await run_fixer(
                        self.svc, command, res.stderr, plan.language, self.trace, self.usage
                    )
                    try:
                        check_command(fix.command, self.svc.policy)
                        command = fix.command
                    except PolicyViolation:
                        await self.trace.log(
                            "install", ref=session.which, tail="fixer command denied by policy"
                        )
            if installed and plan.language == "python" and setup_cmd:
                # A fixer that retried with its own plain `python -m venv` rewrote the
                # venv's pyvenv.cfg and silently dropped --system-site-packages — the
                # preinstalled pytest toolchain disappears and every later test phase
                # reads "No module named pytest". Re-running the FIXED venv step is
                # idempotent and restores the flag (installed packages are untouched).
                await self._exec(session, setup_cmd, "install")
            if not installed:
                all_installed = False
                findings.append(
                    await self._add_finding(
                        Finding(
                            category=FindingCategory.setup_failure,
                            severity=Severity.low,
                            title=f"Install failed on {session.which} after self-heal attempts",
                            proven=True,
                            confidence=0.90,
                            evidence=[Evidence(kind="exec", command=command[:120], excerpt="non-zero exit")],
                        )
                    )
                )
        self._install_ok = all_installed
        return findings

    async def _run_tests(self, base_s: SandboxSession, pr_s: SandboxSession, plan) -> list[Finding]:
        base_res, pr_res = await asyncio.gather(
            self._exec(base_s, plan.test_cmd, "tests"),
            self._exec(pr_s, plan.test_cmd, "tests"),
        )
        if not base_res.ok:
            # A suite that already fails on the base branch gives no baseline — a PR diff
            # against it proves nothing, and "safe" would be a lie. Route to a human.
            self.tests_ran = False
            await self.trace.log(
                "tests",
                ref="base",
                tail="test suite fails on the base branch; cannot establish a baseline",
            )
            return []
        self.tests_ran = True
        if not pr_res.ok and not pr_res.timed_out and pr_res.exit_code not in (124, 137):
            failed_line = next(
                (line for line in pr_res.stderr.splitlines() if "FAILED" in line or "Error" in line),
                pr_res.stderr[:200],
            )
            return [
                await self._add_finding(
                    Finding(
                        category=FindingCategory.test_regression,
                        severity=Severity.high,
                        title="A test that passes on base fails on the PR",
                        proven=True,
                        confidence=0.85,
                        evidence=[
                            Evidence(
                                kind="exec",
                                step_id="sandbox.exec.tests.pr",
                                command=plan.test_cmd[:120],
                                exit_code=pr_res.exit_code,
                                excerpt=failed_line[:300],
                            )
                        ],
                    )
                )
            ]
        return []

    async def _generated_tests(
        self, base_s: SandboxSession, pr_s: SandboxSession, plan, pr
    ) -> list[Finding]:
        if not plan.targets or self.usage.total > self.svc.settings.llm_token_budget_per_run:
            return []
        target = plan.targets[0]  # MVP: one generated test on the top target
        hypothesis = plan.hypotheses.get(target, "")
        target_patch = next((f.patch for f in pr.files if f.path == target), "")
        test = await run_test_writer(
            self.svc,
            target,
            hypothesis,
            plan.language,
            self.trace,
            self.usage,
            target_patch=target_patch,
        )
        if test is None:
            return []
        if plan.language == "node":
            cmd = f"npm test -- {test.path}"
        else:
            cmd = f"python -m pytest -q {test.path}"
        base_ctx = ToolContext(session=base_s, policy=self.svc.policy, run_id=self.run_id, canaries=self.canaries)
        pr_ctx = ToolContext(session=pr_s, policy=self.svc.policy, run_id=self.run_id, canaries=self.canaries)
        try:
            await self.registry.call("test_writer", "write_test_file", {"path": test.path, "content": test.code}, pr_ctx)
            await self.registry.call("test_writer", "write_test_file", {"path": test.path, "content": test.code}, base_ctx)
            base_res, pr_res = await asyncio.gather(
                self.registry.call("runner", "run_command", {"command": cmd, "phase": "tests"}, base_ctx),
                self.registry.call("runner", "run_command", {"command": cmd, "phase": "tests"}, pr_ctx),
            )
        except Exception as e:  # noqa: BLE001 — generated tests are best-effort
            await self.trace.log("generated", tail=f"generated test skipped: {redact(str(e))[:120]}")
            return []
        if base_res.ok and pr_res.ok:
            await self.trace.log("generated", tail="generated test passes on base and PR (kept, no bug)")
            return []
        if not base_res.ok:
            await self.trace.log("generated", tail="generated test does not run on base; discarded")
            return []
        if pr_res.timed_out or pr_res.exit_code in (124, 137):
            return []
        return [
            await self._add_finding(
                Finding(
                    category=FindingCategory.bug_proven,
                    severity=Severity.high,
                    title=f"Generated test for {target} fails on the PR and passes on base",
                    proven=True,
                    confidence=0.95,
                    evidence=[
                        Evidence(
                            kind="exec",
                            step_id="sandbox.exec.generated.pr",
                            command=cmd[:120],
                            exit_code=pr_res.exit_code,
                            excerpt=pr_res.stderr[:300],
                        )
                    ],
                )
            )
        ]

    # ------------------------------------------------------------- observe
    async def _log_base_behaviour(self, base_s: SandboxSession, rep) -> None:
        """The base sandbox is our own baseline. Its signals are recorded for the trace but
        never turned into findings against the PR (the report is
        also used to suppress baseline-matched signals on the PR side)."""
        noisy = rep.network_attempts or rep.canary_hits or rep.fs_denied or rep.limits_hit
        if noisy:
            await self.trace.log(
                "behaviour",
                ref="base",
                tail="baseline sandbox showed unexpected signals; logged, not attributed to the PR",
            )

    async def _observe(self, sessions: list[SandboxSession], baseline=None) -> list[Finding]:
        """Signals from the PR sandbox become findings — except those the BASELINE sandbox
        produced too: a repo that phones home on main would otherwise flag every PR."""
        findings: list[Finding] = []
        for session in sessions:
            rep = await session.behaviour()
            for host in rep.network_attempts:
                if baseline is not None and host in baseline.network_attempts:
                    await self.trace.log(
                        "behaviour",
                        ref=session.which,
                        tail=f"host {host} also attempted on base — baseline behaviour, not attributed",
                    )
                    continue
                severity = Severity.critical if "169.254.169.254" in host else Severity.high
                findings.append(
                    await self._add_finding(
                        Finding(
                            category=FindingCategory.network_attempt,
                            severity=severity,
                            title=f"Code attempted to reach {host} (blocked by the egress policy)",
                            proven=True,
                            confidence=0.90,
                            evidence=[Evidence(kind="behaviour", step_id="sandbox.behaviour", excerpt=host)],
                        )
                    )
                )
                self.counters.network_blocked += 1
                await self.trace.containment("network_blocked", detail=host, ref=session.which)
            canary_hits = [
                h for h in rep.canary_hits
                if baseline is None or h not in baseline.canary_hits
            ]
            if canary_hits:
                findings.append(
                    await self._add_finding(
                        Finding(
                            category=FindingCategory.secret_access,
                            severity=Severity.critical,
                            title="Code read or leaked planted canary secrets",
                            proven=True,
                            confidence=0.90,
                            evidence=[
                                Evidence(
                                    kind="behaviour", step_id="sandbox.behaviour", excerpt=f"canary {name} seen"
                                )
                                for name in rep.canary_hits[:3]
                            ],
                        )
                    )
                )
                self.counters.canary_hits += len(canary_hits)
                await self.trace.containment("canary_hit", detail=", ".join(canary_hits), ref=session.which)
            for denied in rep.fs_denied:
                if baseline is not None and baseline.fs_denied:
                    await self.trace.log(
                        "behaviour",
                        ref=session.which,
                        tail="write denial also seen on base — baseline behaviour, not attributed",
                    )
                    continue
                findings.append(
                    await self._add_finding(
                        Finding(
                            category=FindingCategory.fs_escape_attempt,
                            severity=Severity.critical,
                            title="A write outside the repo was attempted and denied",
                            proven=True,
                            confidence=0.90,
                            evidence=[Evidence(kind="behaviour", step_id="sandbox.behaviour", excerpt=denied)],
                        )
                    )
                )
                self.counters.writes_denied += 1
                await self.trace.containment("write_denied", detail=denied, ref=session.which)
            for limit in rep.limits_hit:
                if self._limit_findings >= 1:
                    continue
                self._limit_findings += 1
                findings.append(
                    await self._add_finding(
                        Finding(
                            category=FindingCategory.resource_abuse,
                            severity=Severity.medium,
                            title=f"Run hit the {limit} limit",
                            proven=True,
                            confidence=0.85,
                            evidence=[Evidence(kind="behaviour", step_id="sandbox.behaviour", excerpt=limit)],
                        )
                    )
                )
                self.counters.limits_hit += 1
                await self.trace.containment("limit_hit", detail=limit, ref=session.which)
        return findings

    # -------------------------------------------------------------- helpers
    async def _persist_usage(self) -> None:
        await self.svc.repo.add_usage(
            self.run_id,
            self.usage.prompt_tokens,
            self.usage.completion_tokens,
            self.usage.llm_calls,
        )

    def _analyst_warranted(self, findings: list[Finding], signals: list[str]) -> bool:
        if self.usage.total > self.svc.settings.llm_token_budget_per_run:
            return False
        behaviour_alert = any(f.category in DANGER or f.category in BREAKING for f in findings)
        static_high = any("+5" in s or "+4" in s for s in signals)
        preflight_warning = bool(findings)
        return behaviour_alert or static_high or preflight_warning

    async def _add_finding(self, finding: Finding) -> Finding:
        saved = await self.svc.repo.add_finding(self.run_id, finding)
        await self.trace.finding(saved)
        return saved

    async def _exec(self, session: SandboxSession, command: str, phase: str):
        self._exec_seq += 1
        key = f"{session.which}:{phase}:{self._exec_seq}"
        await self.trace.span_start("sandbox.exec", key=key, ref=session.which, step=phase)
        ctx = ToolContext(session=session, policy=self.svc.policy, run_id=self.run_id, canaries=self.canaries)
        result = await self.registry.call(
            "runner",
            "run_command",
            {"command": command, "phase": phase},
            ctx,
        )
        await self.trace.span_end(
            "sandbox.exec",
            key=key,
            ref=session.which,
            step=phase,
            cmd=redact(command)[:120],
            exit_code=result.exit_code,
            timed_out=result.timed_out,
        )
        tail = (result.stderr or result.stdout or "")[-300:]
        await self.trace.log(phase, ref=session.which, tail=redact(tail))
        return result

    async def _destroy_all(self) -> None:
        for session in list(self.sessions):
            try:
                await session.destroy()
            except Exception:  # noqa: BLE001
                log.exception("destroy failed for run %s", self.run_id)
            finally:
                if session in self.sessions:
                    self.sessions.remove(session)
        if not self._destroy_emitted:
            self._destroy_emitted = True
            await self.trace.span_end("sandbox.destroy", sandboxes_alive=0)

    def _checkpoint(self) -> None:
        if self.svc.queue.is_cancelled(self.run_id):
            raise RunCancelled()
