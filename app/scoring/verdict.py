"""Deterministic verdict: a rule table, not the model.
Checks run top to bottom, first match wins."""
from __future__ import annotations

from app.guardrails.policy import Policy
from app.schemas import Finding, FindingCategory, Route, VerdictLabel

DANGER = {
    FindingCategory.known_malicious_dependency,
    FindingCategory.secret_access,
    FindingCategory.network_attempt,
    FindingCategory.fs_escape_attempt,
    FindingCategory.prompt_injection,
}
BREAKING = {
    FindingCategory.test_regression,
    FindingCategory.bug_proven,
    FindingCategory.resource_abuse,
}

SAFE_TO_MERGE_CONFIDENCE = 0.82
INCONCLUSIVE_CONFIDENCE = 0.30


def verdict_from_findings(
    findings: list[Finding], *, tests_ran: bool
) -> tuple[VerdictLabel, float, list[str]]:
    danger = [f for f in findings if f.category in DANGER]
    if danger:
        # Confidence comes from the evidence behind the strongest dangerous finding —
        # pre-flight advisories carry their own proven confidence (0.95), so this is
        # never a max() over an empty set.
        conf = max(f.confidence for f in danger)
        reasons = [f"{f.category.value} found ({f.id})" for f in danger]
        return VerdictLabel.suspicious, conf, reasons

    breaking = [f for f in findings if f.proven and f.category in BREAKING]
    if breaking:
        conf = max(f.confidence for f in breaking)
        reasons = [f"{f.category.value} proven ({f.id})" for f in breaking]
        return VerdictLabel.needs_changes, conf, reasons

    if not tests_ran:
        return VerdictLabel.inconclusive, INCONCLUSIVE_CONFIDENCE, ["tests could not be executed"]

    return (
        VerdictLabel.safe_to_merge,
        SAFE_TO_MERGE_CONFIDENCE,
        ["all tests pass on base and PR; no risky behaviour"],
    )


def route_for(label: VerdictLabel, confidence: float, policy: Policy) -> Route:
    if label is VerdictLabel.suspicious:
        return Route.human_review  # maker-checker: always a human
    if label is VerdictLabel.inconclusive:
        return Route.human_review
    if label is VerdictLabel.needs_changes and confidence < policy.auto_threshold:
        return Route.human_review
    return Route.auto
