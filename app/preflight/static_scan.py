"""Static risk scan of the changed files (cheap rules, GuardDog-style) and the high-ROI
risk ranking that feeds the Planner (workbook: High-ROI strategic planning)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import PRInfo


@dataclass(frozen=True)
class Rule:
    name: str
    rx: object
    score: int
    reason: str


RULES: list[Rule] = [
    Rule("metadata_probe", r"169\.254\.169\.254|metadata\.google|latest/meta-data", 5, "cloud metadata probe"),
    Rule("install_hook", r"postinstall|preinstall|setup\.py|easy_install|entry_points", 5, "install hook touched"),
    Rule("code_exec", r"subprocess|os\.system|os\.popen|\bexec\(|\beval\(", 4, "code execution"),
    Rule("obfuscation", r"base64|b64decode|zlib\.decompress|codecs\.decode", 4, "obfuscation"),
    Rule("network", r"requests\.(get|post)|urllib|http\.client|https?://|fetch\(", 3, "network access"),
    Rule("secrets_env", r"environ\[|process\.env|getenv", 3, "environment secret access"),
    Rule("input_handling", r"def parse|\.split\(|open\(|input\(", 2, "input handling"),
]

_COMPILED = [(r.name, re.compile(r.rx), r.score, r.reason) for r in RULES]


@dataclass(frozen=True)
class RiskSignal:
    path: str
    rule: str
    score: int
    reason: str


def scan_diff(pr: PRInfo) -> list[RiskSignal]:
    signals: list[RiskSignal] = []
    for f in pr.files:
        for name, rx, score, reason in _COMPILED:
            if rx.search(f.patch):
                signals.append(RiskSignal(path=f.path, rule=name, score=score, reason=reason))
    return signals


def rank_files(pr: PRInfo, top: int = 3) -> list[tuple[str, list[str], int]]:
    """Score changed files; the planner gets the top N with reasons. Test files rank lower."""
    scores: dict[str, int] = {}
    reasons: dict[str, list[str]] = {}
    for signal in scan_diff(pr):
        scores[signal.path] = scores.get(signal.path, 0) + signal.score
        reasons.setdefault(signal.path, []).append(signal.reason)
    for f in pr.files:
        scores.setdefault(f.path, 0)
        reasons.setdefault(f.path, [])
        if f.path.startswith("tests/") or "/test_" in f.path:
            scores[f.path] -= 2
        scores[f.path] += min(len(f.patch) // 2000, 2)  # size of change
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(path, reasons[path], score) for path, score in ranked[:top]]
