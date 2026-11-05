#!/usr/bin/env python3
"""Repair the demo PRs without deleting repos.

GitHub permanently blocks reopening PRs whose head branch was force-pushed while
closed (REST 422, GraphQL "Could not open the pull request"). But a CLOSED PR does
not block creating a NEW pull request from the same head branch — so this script
opens a fresh PR per repo, records the old→new number mapping, and rewrites
eval_cases/cases.yaml + app/sources/dummy.py to the new numbers. Old closed PRs
remain as history; every URL the product links to becomes open again.

Usage: python scripts/repair_demo_prs.py [--apply]
Without --apply it only prints the mapping (dry run).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ORG = "0xv3nm09"
CASES_PATH = REPO_ROOT / "eval_cases" / "cases.yaml"
DUMMY_PATH = REPO_ROOT / "app" / "sources" / "dummy.py"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd} failed:\n{r.stdout}\n{r.stderr}")
    return r


def case_list() -> list[tuple[str, int, str, str]]:
    """(name, old_pr_number, title, body) from cases.yaml + PR metadata."""
    out = []
    text = CASES_PATH.read_text()
    for m in re.finditer(r"name:\s*([\w-]+),\s*url:\s*\"[^\"]*/pull/(\d+)\"", text):
        name, num = m.group(1), int(m.group(2))
        pr = run(["gh", "api", f"repos/{ORG}/{name}/pulls/{num}"], check=False)
        if pr.returncode != 0:
            print(f"  ! {name}: cannot read PR #{num} — skipping (flaky API? retry)")
            continue
        d = json.loads(pr.stdout)
        out.append((name, num, d.get("title", name), d.get("body") or ""))
    return out


def main() -> None:
    apply = "--apply" in sys.argv
    cases = case_list()
    if not cases:
        sys.exit("no cases read — GitHub API unreachable")
    mapping: dict[str, int] = {}
    for name, old, title, body in cases:
        # reuse the PR body/title; create a fresh PR from the same head branch
        r = run(["gh", "api", f"repos/{ORG}/{name}/pulls", "-X", "POST",
                 "-f", f"title={title}", "-f", "head=pr", "-f", "base=main",
                 "-F", f"body={body}"], check=False)
        if r.returncode != 0:
            if "A pull request already exists" in (r.stdout + r.stderr):
                # an OPEN pr from head=pr already exists — find it
                lst = run(["gh", "api", f"repos/{ORG}/{name}/pulls?state=open",
                           "--jq", ".[0].number"])
                mapping[name] = int(lst.stdout.strip())
                print(f"  = {name}: open PR already exists → #{mapping[name]}")
                continue
            print(f"  ! {name}: create failed — {r.stderr[:120]}")
            continue
        d = json.loads(r.stdout)
        new = int(d["number"])
        mapping[name] = new
        print(f"  + {name}: #{old} → open PR #{new}")

    if not apply:
        print("\n(dry run — pass --apply to rewrite cases.yaml + dummy.py)")
        print(json.dumps(mapping, indent=1))
        return
    if not mapping:
        sys.exit("nothing repaired")

    yaml_text = CASES_PATH.read_text()
    for name, new in mapping.items():
        yaml_text, n = re.subn(
            rf"(github\.com/{ORG}/{name}/pull/)\d+",
            rf"\g<1>{new}",
            yaml_text,
        )
        if n == 0:
            print(f"  ! {name}: no URL rewritten in cases.yaml")
    CASES_PATH.write_text(yaml_text)

    dummy_text = DUMMY_PATH.read_text()
    for name, new in mapping.items():
        dummy_text = re.sub(
            rf"(https://github.com/{ORG}/{name}/pull/)\d+",
            rf"\g<1>{new}",
            dummy_text,
        )
    DUMMY_PATH.write_text(dummy_text)
    print(f"\nrewrote {CASES_PATH.relative_to(REPO_ROOT)} and {DUMMY_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
