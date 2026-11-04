"""Real GitHub source for public PRs. Lifts the 60 req/h anonymous limit with a read-only
token; private repos are out of scope (workbook: Scope)."""
from __future__ import annotations

import re
from typing import Literal

import httpx

from app.core.config import Settings
from app.core.errors import Unavailable
from app.guardrails.input import parse_pr_url
from app.schemas import Dep, PRFile, PRInfo

SKIP_DEP_KEYS = {"name", "version", "main", "description", "license", "private", "type", "scripts"}

VERSION_SPEC_RE = re.compile(r"[=<>~!^]+(\d[\w.]*)")


class GitHubSource:
    name = "github"

    def __init__(self, settings: Settings):
        token = settings.github_token.get_secret_value()
        self._headers = {"Accept": "application/vnd.github+json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://api.github.com", headers=self._headers, timeout=30
        )

    async def get_pr(self, url: str) -> PRInfo:
        owner, repo, number = parse_pr_url(url)
        async with self._client() as c:
            pr = await self._get(c, f"/repos/{owner}/{repo}/pulls/{number}")
            files = await self._get_list(c, f"/repos/{owner}/{repo}/pulls/{number}/files")
        title = str(pr.get("title", ""))
        body = str(pr.get("body") or "")
        base_ref = str((pr.get("base") or {}).get("ref", "main"))
        pr_files = [
            PRFile(path=str(f.get("filename", "")), patch=str(f.get("patch", "")))
            for f in files
        ][:50]
        language: Literal["python", "node"] = self._detect_language(files)
        return PRInfo(
            url=url,
            owner=owner,
            repo=repo,
            number=number,
            title=title,
            body=body,
            language=language,
            base_ref=base_ref,
            files=pr_files,
            deps=self._deps_from_files(pr_files),
        )

    async def fetch_tarball(self, owner: str, repo: str, ref: str) -> bytes:
        """Repo snapshot for sandbox materialization: base branch or refs/pull/N/head."""
        async with self._client() as c:
            r = await c.get(f"/repos/{owner}/{repo}/tarball/{ref}", follow_redirects=True)
        if r.status_code == 404:
            raise Unavailable("repository or ref not found")
        if r.status_code == 403:
            raise Unavailable("GitHub rate limit hit; set AIRLOCK_GITHUB_TOKEN")
        r.raise_for_status()
        return r.content

    @staticmethod
    async def _get(client: httpx.AsyncClient, path: str) -> dict:
        r = await client.get(path)
        if r.status_code == 404:
            raise Unavailable("PR not found or not public")
        if r.status_code == 403:
            raise Unavailable("GitHub rate limit hit; set AIRLOCK_GITHUB_TOKEN")
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else {}

    @staticmethod
    async def _get_list(client: httpx.AsyncClient, path: str) -> list:
        r = await client.get(path)
        if r.status_code == 404:
            raise Unavailable("PR not found or not public")
        if r.status_code == 403:
            raise Unavailable("GitHub rate limit hit; set AIRLOCK_GITHUB_TOKEN")
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    @staticmethod
    def _detect_language(files: list) -> Literal["python", "node"]:
        paths = [str(f.get("filename", "")) for f in files]
        # .mjs/.cjs matter: fresh repos often report language=null from GitHub linguist
        # (stats are computed asynchronously), so the diff is the reliable signal.
        if any(p.endswith((".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", "package.json")) for p in paths):
            return "node"
        return "python"

    @staticmethod
    def _deps_from_files(files: list[PRFile]) -> list[Dep]:
        """Dependencies added by the PR, parsed from the diff: requirements*.txt lines and
        package.json entries. This is what makes the pre-flight OSV check work on real PRs."""
        deps: list[Dep] = []
        for f in files:
            if f.path.startswith("requirements") and f.path.endswith(".txt"):
                for line in f.patch.splitlines():
                    if not line.startswith("+") or line.startswith("+++"):
                        continue
                    spec = line[1:].strip()
                    if not spec or spec.startswith(("#", "-")):
                        continue
                    name = re.split(r"[<>=~!\[\s;,]", spec)[0].strip()
                    if not name:
                        continue
                    m = VERSION_SPEC_RE.search(spec)
                    deps.append(
                        Dep(ecosystem="PyPI", name=name, version=m.group(1) if m else None, is_new=True)
                    )
            elif f.path.endswith("package.json"):
                for line in f.patch.splitlines():
                    if not line.startswith("+"):
                        continue
                    m = re.search(r'\+\s*"([^"]+)"\s*:\s*"([^"]*)"', line)
                    if not m:
                        continue
                    key, value = m.group(1), m.group(2)
                    if key in SKIP_DEP_KEYS:
                        continue
                    vm = re.match(r"[\^>=~]*v?(\d[\w.\-]*)", value)
                    deps.append(
                        Dep(
                            ecosystem="npm",
                            name=key,
                            version=vm.group(1) if vm else None,
                            is_new=True,
                        )
                    )
        seen: set[str] = set()
        unique: list[Dep] = []
        for d in deps:
            if f"{d.ecosystem}:{d.name}" in seen:
                continue
            seen.add(f"{d.ecosystem}:{d.name}")
            unique.append(d)
        return unique[:50]
