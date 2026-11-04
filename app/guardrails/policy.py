"""Versioned policy file (policies/policy_v1.yaml): allowed commands, denied patterns,
thresholds. The version is stamped on every run so old verdicts stay reproducible."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Policy:
    version: str
    effective_from: str
    raw: dict
    _denied: list[re.Pattern] = field(default_factory=list, repr=False)

    @classmethod
    def load(cls, path: str | Path) -> "Policy":
        data = yaml.safe_load(Path(path).read_text())
        denied = [re.compile(p) for p in data.get("denied_patterns", [])]
        return cls(
            version=str(data["version"]),
            effective_from=str(data.get("effective_from", "")),
            raw=data,
            _denied=denied,
        )

    @property
    def allowed_prefixes(self) -> list[str]:
        out: list[str] = []
        for cmds in self.raw.get("allowed_commands", {}).values():
            out.extend(cmds)
        return out

    @property
    def denied_patterns(self) -> list[re.Pattern]:
        return self._denied

    def allowed_commands(self, language: str) -> list[str]:
        return list(self.raw.get("allowed_commands", {}).get(language, []))

    @property
    def install_timeout_s(self) -> int:
        return int(self.raw.get("sandbox", {}).get("install_timeout_s", 180))

    @property
    def test_timeout_s(self) -> int:
        return int(self.raw.get("sandbox", {}).get("test_timeout_s", 120))

    @property
    def auto_threshold(self) -> float:
        return float(self.raw.get("auto_verdict_threshold", 0.80))

    @property
    def max_generated_tests(self) -> int:
        return int(self.raw.get("generated_tests", {}).get("max_per_run", 3))

    @property
    def max_generated_chars(self) -> int:
        return int(self.raw.get("generated_tests", {}).get("max_chars", 6000))
