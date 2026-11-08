"""Output guardrails: secret redaction (incl. planted canaries) and the command policy."""
from __future__ import annotations

import re

from app.core.errors import PolicyViolation
from app.guardrails.policy import Policy

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

# Blocked writes on the read-only root surface in stderr — this is the detector for the
# `rm -rf` containment moment (fs_escape_attempt), since container.diff() only sees
# writes that actually happened.
DENIED_WRITE_MARKER = re.compile(
    r"Read-only file system|Permission denied|Operation not permitted", re.I
)

METADATA_IP = "169.254.169.254"

# Shell metacharacters: none of the allow-listed commands (pip install -r, pytest, npm
# test) ever need them, so their presence is an injection attempt — command chaining
# (`;`, `&&`, `|`), substitution (`$(`, backticks), redirections, subshells, newlines.
SHELL_META = re.compile(r"[;|&`$\n\r><]|\)\s*[({;]")

# pip-installed arguments: `-r/--requirement <file>` or plain name specs (name, name==1.2,
# name[extra], ".", "-e ."). Anything else (URLs, git refs, local paths with odd chars)
# is rejected — pip executes setup.py from what it installs.
PIP_ARG = re.compile(r"[A-Za-z0-9._\-+=\[\],]+")
PIP_FILE = re.compile(r"[\w.\-/]+")


def redact(text: str) -> str:
    for name, rx in SECRET_PATTERNS:
        text = rx.sub(f"[REDACTED:{name}]", text)
    return text


def redact_with_canaries(text: str, canary_values: dict[str, str]) -> str:
    """Canary values are replaced first so their presence stays detectable as [CANARY];
    every other secret-like string becomes [REDACTED:<kind>]."""
    for value in canary_values.values():
        if value:
            text = text.replace(value, "[CANARY]")
    return redact(text)


def check_command(command: str, policy: Policy) -> None:
    """Gate 4 of the tool registry, hardened:
    1. metacharacters rejected (kills `;`, `&&`, `|`, `$()`, backticks, redirects, newlines),
    2. deny patterns,
    3. allow-list by TOKEN boundary — `pytestx` is not `pytest` (startswith() was bypassable),
    4. pip installs restricted to -r/--requirement files and plain name specs.
    """
    cmd = command.strip()
    if SHELL_META.search(cmd):
        raise PolicyViolation(f"shell metacharacters are not allowed: {cmd[:80]}")
    for rx in policy.denied_patterns:
        if rx.search(cmd):
            raise PolicyViolation(f"command denied by policy: {cmd[:80]}")
    tokens = cmd.split()
    matched: list[str] | None = None
    for prefix in policy.allowed_prefixes:
        parts = prefix.split()
        if len(tokens) >= len(parts) and tokens[: len(parts)] == parts:
            matched = parts
            break
    if matched is None:
        raise PolicyViolation(
            f"command not in allow-list: {cmd[:80]} (allowed: {', '.join(policy.allowed_prefixes)})"
        )
    if matched[-2:] == ["pip", "install"] or matched[:2] == ["pip", "install"]:
        args = tokens[len(matched) :]
        i = 0
        while i < len(args):
            arg = args[i]
            if arg in ("-r", "--requirement"):
                if i + 1 >= len(args) or not PIP_FILE.fullmatch(args[i + 1]):
                    raise PolicyViolation(f"bad requirements file argument: {arg}")
                i += 2
            elif PIP_ARG.fullmatch(arg):
                i += 1
            else:
                raise PolicyViolation(f"unsupported pip argument: {arg[:60]}")
