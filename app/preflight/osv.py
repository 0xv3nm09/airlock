"""Pre-flight dependency checks: OSV batch lookup for known-malicious packages (MAL-)
and package age. Runs outside the sandbox, before any code executes."""
from __future__ import annotations

from typing import Protocol

import httpx

from app.schemas import Dep, Evidence, Finding, FindingCategory, Severity

MAL_URL = "https://api.osv.dev/v1/querybatch"
MIN_PACKAGE_AGE_DAYS = 3


class OSVClient(Protocol):
    async def query(self, deps: list[Dep]) -> dict[str, list[str]]: ...


class AgeLookup(Protocol):
    async def age_days(self, dep: Dep) -> float | None: ...


class HttpxOSV:
    """Real OSV batch API: up to 1,000 queries/request; returns vulnerability IDs only."""

    async def query(self, deps: list[Dep]) -> dict[str, list[str]]:
        if not deps:
            return {}
        queries = [
            {"package": {"name": d.name, "ecosystem": d.ecosystem}, **({"version": d.version} if d.version else {})}
            for d in deps
        ]
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(MAL_URL, json={"queries": queries})
            r.raise_for_status()
            results = r.json().get("results", [])
        out: dict[str, list[str]] = {}
        for dep, res in zip(deps, results):
            vulns = res.get("vulns", []) if isinstance(res, dict) else []
            out[dep.name] = [str(v.get("id")) for v in vulns if isinstance(v, dict)]
        return out


class DummyOSV:
    KNOWN: dict[str, list[str]] = {"imaginary-exfil-pkg": ["MAL-2026-DEMO-0001"]}

    async def query(self, deps: list[Dep]) -> dict[str, list[str]]:
        return {d.name: list(self.KNOWN.get(d.name, [])) for d in deps}


class HttpxAgeLookup:
    """Registry metadata: PyPI JSON / npm registry publish time. Fails open (None)."""

    async def age_days(self, dep: Dep) -> float | None:
        if not dep.version:
            return None
        try:
            if dep.ecosystem == "PyPI":
                url = f"https://pypi.org/pypi/{dep.name}/json"
            else:
                url = f"https://registry.npmjs.org/{dep.name}"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()
            times = data.get("releases", {}).get(dep.version) or data.get("time", {}).get(dep.version)
            from datetime import datetime, timezone

            if isinstance(times, list) and times:
                stamp = times[0].get("upload_time_iso_8601")
            elif isinstance(times, str):
                stamp = times
            else:
                return None
            published = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - published).total_seconds() / 86400
        except Exception:
            return None


class DummyAgeLookup:
    async def age_days(self, dep: Dep) -> float | None:
        return None


async def check_known_malicious(deps: list[Dep], osv: OSVClient) -> list[Finding]:
    if not deps:
        return []
    hits = await osv.query(deps)
    findings: list[Finding] = []
    for dep in deps:
        for advisory in hits.get(dep.name, []):
            if advisory.startswith("MAL-"):
                findings.append(
                    Finding(
                        category=FindingCategory.known_malicious_dependency,
                        severity=Severity.critical,
                        title=f"Dependency {dep.name}@{dep.version or '?'} matches known-malicious advisory {advisory}",
                        proven=True,
                        confidence=0.95,
                        evidence=[Evidence(kind="advisory", excerpt=advisory)],
                    )
                )
    return findings


async def check_package_age(deps: list[Dep], age: AgeLookup) -> list[Finding]:
    findings: list[Finding] = []
    for dep in deps:
        if not dep.is_new:
            continue
        days = await age.age_days(dep)
        if days is not None and days < MIN_PACKAGE_AGE_DAYS:
            findings.append(
                Finding(
                    category=FindingCategory.young_package,
                    severity=Severity.medium,
                    title=f"Dependency {dep.name}@{dep.version or '?'} was published {days:.1f} days ago (< {MIN_PACKAGE_AGE_DAYS})",
                    proven=False,
                    confidence=0.60,
                    evidence=[Evidence(kind="registry", excerpt=f"age_days={days:.2f}")],
                )
            )
    return findings
