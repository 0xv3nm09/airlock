"""Input guardrails: strict PR-URL parsing (SSRF-safe) and the prompt-injection screen."""
from __future__ import annotations

import re

from app.core.errors import InvalidPRUrl

PR_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[\w.\-]+)/(?P<repo>[\w.\-]+)/pull/(?P<number>\d+)/?$"
)

# Conservative starting set; precision on `suspicious` is measured by the benchmark.
# Directive-shaped only: mentioning "AI reviewer" without an imperative verb is normal PR
# prose ("AI reviewer: this PR only touches docs" must NOT flag).
INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_instructions", re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I)),
    ("approve_directive", re.compile(r"(mark|approve)\s+(this\s+)?(pr|pull request)\s+as\s+(safe|approved)", re.I)),
    ("role_hijack", re.compile(r"(you are now|act as)\s+(the\s+)?(reviewer|admin|system)", re.I)),
    (
        "ai_reviewer_directive",
        re.compile(
            r"AI reviewer\s*:\s*[^.\n]{0,40}?"
            r"(approve|mark\s+as|ignore|skip|disable|bypass|merge|pass\s+this)",
            re.I,
        ),
    ),
    ("disregard", re.compile(r"disregard\s+(all\s+)?(previous|prior|your)\s+(instructions|rules)", re.I)),
]


def parse_pr_url(url: str) -> tuple[str, str, int]:
    m = PR_URL_RE.match(url.strip())
    if not m:
        raise InvalidPRUrl(
            "pr_url must look like https://github.com/<owner>/<repo>/pull/<number>"
        )
    return m.group("owner"), m.group("repo"), int(m.group("number"))


def scan_prompt_injection(
    title: str, body: str, diff_text: str
) -> list[tuple[str, str, str]]:
    """Returns (rule, where, excerpt) hits. PR text is data, never instructions."""
    hits: list[tuple[str, str, str]] = []
    for label, text in (("title", title), ("body", body), ("diff", diff_text)):
        for rule, rx in INJECTION_PATTERNS:
            m = rx.search(text)
            if m:
                start = max(0, m.start() - 40)
                hits.append((rule, label, text[start : m.end() + 60].strip()))
    return hits
