"""End-to-end dummy pipeline tests: scenario in, verdict + findings + clean lifecycle out."""
import pytest

from app.agents.orchestrator import execute_run
from app.core.config import Settings
from app.sandbox.dummy import DummySandbox
from app.schemas import RunStatus, VerdictLabel
from app.services import build_services


@pytest.fixture()
async def svc():
    services = build_services(Settings())
    yield services


async def _run(svc, url: str):
    run = await svc.repo.create_run(owner_id="test", pr_url=url, policy_version=svc.policy.version)
    await execute_run(svc, run.id, url)
    record = svc.repo.get_record(run.id)
    assert record is not None
    return record


async def test_malicious_exfil_is_suspicious_with_canary(svc):
    before = DummySandbox.alive
    record = await _run(svc, "https://github.com/0xv3nm09/setup-py-exfil/pull/6")
    out = record.out
    assert out.status is RunStatus.completed
    assert out.verdict is not None and out.verdict.label is VerdictLabel.suspicious
    assert out.verdict.route.value == "human_review"
    cats = {f.category.value for f in out.findings}
    assert {"network_attempt", "secret_access"} <= cats
    assert out.counters.network_blocked >= 1
    assert out.counters.canary_hits >= 1
    assert DummySandbox.alive == before, "all sandboxes must be destroyed"


async def test_clean_repo_is_safe(svc):
    record = await _run(svc, "https://github.com/0xv3nm09/clean-lib/pull/1")
    assert record.out.verdict is not None
    assert record.out.verdict.label is VerdictLabel.safe_to_merge
    assert record.out.findings == []


async def test_regression_is_needs_changes(svc):
    record = await _run(svc, "https://github.com/0xv3nm09/regression-unicode/pull/3")
    assert record.out.verdict is not None
    assert record.out.verdict.label is VerdictLabel.needs_changes
    assert record.out.verdict.route.value == "auto"
    cats = {f.category.value for f in record.out.findings}
    assert "test_regression" in cats


async def test_known_malicious_dep_stops_before_sandbox(svc):
    created_before = DummySandbox.created
    record = await _run(svc, "https://github.com/0xv3nm09/known-malicious-dep/pull/16")
    assert record.out.verdict is not None
    assert record.out.verdict.label is VerdictLabel.suspicious
    cats = {f.category.value for f in record.out.findings}
    assert "known_malicious_dependency" in cats
    assert DummySandbox.created == created_before, "pre-flight must stop the run with no sandbox"
    assert DummySandbox.alive == 0


async def test_setup_fail_self_heals(svc):
    record = await _run(svc, "https://github.com/0xv3nm09/setup-fail/pull/5")
    assert record.out.verdict is not None
    assert record.out.verdict.label is VerdictLabel.safe_to_merge
    span_names = {e.name for e in record.events}
    assert "agent.fixer" in span_names, "self-heal must be visible in the trace"


async def test_rm_rf_is_denied_and_flagged(svc):
    record = await _run(svc, "https://github.com/0xv3nm09/rm-rf-test/pull/8")
    assert record.out.verdict is not None
    assert record.out.verdict.label is VerdictLabel.suspicious
    cats = {f.category.value for f in record.out.findings}
    assert "fs_escape_attempt" in cats
    assert record.out.counters.writes_denied >= 1


async def test_edge_crash_proves_bug_with_generated_test(svc):
    record = await _run(svc, "https://github.com/0xv3nm09/edge-crash/pull/4")
    assert record.out.verdict is not None
    assert record.out.verdict.label is VerdictLabel.needs_changes
    cats = {f.category.value for f in record.out.findings}
    assert "bug_proven" in cats


async def test_metadata_probe_is_critical(svc):
    record = await _run(svc, "https://github.com/0xv3nm09/metadata-probe/pull/9")
    assert record.out.verdict is not None
    assert record.out.verdict.label is VerdictLabel.suspicious
    critical = [f for f in record.out.findings if f.category.value == "network_attempt"]
    assert critical and critical[0].severity.value == "critical"


async def test_fork_bomb_hits_limit(svc):
    record = await _run(svc, "https://github.com/0xv3nm09/fork-bomb/pull/10")
    assert record.out.verdict is not None
    assert record.out.verdict.label is VerdictLabel.needs_changes
    cats = {f.category.value for f in record.out.findings}
    assert "resource_abuse" in cats


async def test_sleeper_is_the_expected_miss(svc):
    record = await _run(svc, "https://github.com/0xv3nm09/sleeper/pull/17")
    assert record.out.verdict is not None
    assert record.out.verdict.label is VerdictLabel.safe_to_merge, "honest limit: sleepers are missed"


async def test_events_form_a_replayable_trace(svc):
    record = await _run(svc, "https://github.com/0xv3nm09/setup-py-exfil/pull/6")
    types = [e.type for e in record.events]
    assert types[0] == "status"
    assert types[-1] == "status"
    assert "span_start" in types and "span_end" in types
    assert "containment" in types and "verdict" in types
    seqs = [e.seq for e in record.events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs), "seq must be unique and ordered"


async def test_broken_baseline_is_inconclusive_not_safe(svc):
    """Oct 29 audit regression: tests failing on BOTH base and PR must never read safe."""
    record = await _run(svc, "https://github.com/0xv3nm09/broken-baseline/pull/18")
    assert record.out.verdict is not None
    assert record.out.verdict.label is VerdictLabel.inconclusive
    assert record.out.verdict.route.value == "human_review"


async def test_unfixable_install_is_inconclusive_not_safe(svc):
    """Install that self-heal can't fix -> setup_failure -> tests skipped -> inconclusive."""
    record = await _run(svc, "https://github.com/0xv3nm09/install-broken/pull/19")
    assert record.out.verdict is not None
    assert record.out.verdict.label is VerdictLabel.inconclusive
    assert record.out.verdict.route.value == "human_review"
    cats = {f.category.value for f in record.out.findings}
    assert "setup_failure" in cats


async def test_base_branch_signals_are_not_blamed_on_the_pr(svc):
    """Base-sandbox signals are logged, never turned into PR findings."""
    record = await _run(svc, "https://github.com/0xv3nm09/clean-lib/pull/1")
    cats = {f.category.value for f in record.out.findings}
    assert "network_attempt" not in cats and "fs_escape_attempt" not in cats
