"""Verdict rule table tests, including the pre-flight-only confidence regression."""
from app.core.config import REPO_ROOT
from app.guardrails.policy import Policy
from app.schemas import Finding, FindingCategory, Route, Severity, VerdictLabel
from app.scoring.verdict import route_for, verdict_from_findings


def make(category: str, confidence: float, proven: bool = True) -> Finding:
    return Finding(
        category=FindingCategory(category),
        severity=Severity.critical,
        title="t",
        proven=proven,
        confidence=confidence,
    )


def test_danger_is_suspicious_always_human():
    label, conf, _ = verdict_from_findings([make("secret_access", 0.90)], tests_ran=True)
    assert label is VerdictLabel.suspicious
    assert conf == 0.90
    assert route_for(label, conf, _policy()) is Route.human_review


def test_preflight_only_hit_has_confidence():
    """Regression: a MAL- advisory with no sandbox findings must not max() over empty."""
    label, conf, _ = verdict_from_findings(
        [make("known_malicious_dependency", 0.95)], tests_ran=False
    )
    assert label is VerdictLabel.suspicious
    assert conf == 0.95


def test_proven_breaking_is_needs_changes_auto():
    label, conf, _ = verdict_from_findings([make("test_regression", 0.85)], tests_ran=True)
    assert label is VerdictLabel.needs_changes
    assert conf == 0.85
    assert route_for(label, conf, _policy()) is Route.auto


def test_low_confidence_breaking_escalates():
    label, conf, _ = verdict_from_findings([make("bug_proven", 0.55)], tests_ran=True)
    assert label is VerdictLabel.needs_changes
    assert route_for(label, conf, _policy()) is Route.human_review


def test_safe_and_inconclusive():
    label, conf, _ = verdict_from_findings([], tests_ran=True)
    assert (label, conf) == (VerdictLabel.safe_to_merge, 0.82)
    label2, conf2, _ = verdict_from_findings([], tests_ran=False)
    assert (label2, conf2) == (VerdictLabel.inconclusive, 0.30)
    assert route_for(label2, conf2, _policy()) is Route.human_review


def test_setup_failure_cannot_read_safe():
    """Oct 29 audit regression: install failed → tests meaningless → inconclusive, human."""
    label, conf, _ = verdict_from_findings([make("setup_failure", 0.90)], tests_ran=False)
    assert label is VerdictLabel.inconclusive
    assert route_for(label, conf, _policy()) is Route.human_review


def test_both_sides_failing_tests_cannot_read_safe():
    """A suite that fails on base AND PR must not fall through to safe_to_merge."""
    label, _, _ = verdict_from_findings([], tests_ran=False)
    assert label is VerdictLabel.inconclusive


def _policy() -> Policy:
    return Policy.load(REPO_ROOT / "policies" / "policy_v1.yaml")
