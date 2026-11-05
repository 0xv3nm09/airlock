#!/usr/bin/env python3
"""Apply payload fixes to demo PR branches via NORMAL pushes (no force-push).

The full publisher rebuilds repo history and force-pushes main+pr — force-pushing
the base branch is what trips GitHub into closing PRs (and blocking their reopen).
This script instead clones the pr branch, edits the payload files in place, and
pushes a normal commit on top — open PRs follow their head branch automatically.

Fixes applied (matches the payload definitions in publish_demo_repos.py):
  rm-rf-test      + [tool.pytest.ini_options] addopts="-s" in pyproject.toml
  metadata-probe  + addopts="-s" + stderr print of the refused host
  obfuscated-exec + stderr line phrased for the behaviour scan's host regex
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

ORG = "0xv3nm09"

EDITS: dict[str, dict[str, tuple[str, str]]] = {
    # repo -> {path: (old_substr, new_substr)}
    "rm-rf-test": {
        "pyproject.toml": (
            '[project]\nname = "rm-rf-test"\nversion = "0.1.0"\n',
            '[project]\nname = "rm-rf-test"\nversion = "0.1.0"\n\n[tool.pytest.ini_options]\naddopts = "-s"\n',
        ),
    },
    "metadata-probe": {
        "pyproject.toml": (
            '[project]\nname = "metadata-probe"\nversion = "0.1.0"\n',
            '[project]\nname = "metadata-probe"\nversion = "0.1.0"\n\n[tool.pytest.ini_options]\naddopts = "-s"\n',
        ),
        "tests/test_cloud.py": (
            "import urllib.request\n",
            "import sys\nimport urllib.request\n",
        ),
        "tests/test_cloud.py::": (
            "    except Exception as e:\n        raise AssertionError(f'cloud metadata probe to 169.254.169.254 refused: {e}')",
            "    except Exception as e:\n"
            "        print(f'could not connect to 169.254.169.254: {e}', file=sys.stderr)\n"
            "        raise AssertionError(f'cloud metadata probe refused: {e}')",
        ),
    },
    "obfuscated-exec": {
        "setup.py": (
            "    print(f'update-check to pastebin-evil.example failed: {_e}', file=sys.stderr)",
            "    print(f'could not connect to pastebin-evil.example: {_e}', file=sys.stderr)",
        ),
    },
}


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{r.stdout}\n{r.stderr}")
    return r


def main() -> None:
    run(["gh", "auth", "setup-git"], Path(tempfile.gettempdir()))
    for repo, edits in EDITS.items():
        tmp = Path(tempfile.mkdtemp(prefix=f"fix-{repo}-"))
        try:
            run(["git", "clone", "-q", "--branch", "pr", f"https://github.com/{ORG}/{repo}.git", "."], tmp)
            changed = False
            applied: set[str] = set()
            for path, edits_pair in edits.items():
                real = path.rstrip(":")
                f = tmp / real
                if not f.exists():
                    print(f"  ! {repo}/{real}: missing on pr branch — clone/inspect")
                    continue
                content = f.read_text()
                old, new = edits_pair
                if new in content:
                    print(f"  = {repo}/{path}: already fixed")
                    continue
                if old not in content:
                    print(f"  ! {repo}/{path}: expected fragment missing — inspect manually")
                    continue
                f.write_text(content.replace(old, new))
                applied.add(real)
                changed = True
            if not changed:
                continue
            run(["git", "add", "-A"], tmp)
            run(["git", "-c", "user.name=airlock-demo", "-c", "user.email=demo@airlock.local",
                 "commit", "-q", "-m", "sandbox-evidence fixes: loud stderr + uncaptured pytest output"], tmp)
            run(["git", "push", "-q", "origin", "pr"], tmp)  # normal push — no force
            print(f"  + {repo}: pr branch updated (open PR follows head)")
        finally:
            run(["rm", "-rf", str(tmp)], cwd=Path("/tmp"))


if __name__ == "__main__":
    main()
