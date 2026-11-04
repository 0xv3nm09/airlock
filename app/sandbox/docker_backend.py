"""Docker + gVisor (runsc) sandbox backend. Runs on the Vultr VM (tickets T11/T12).

Containment model (fixed in the Oct 29 audit):
- Containers are created with network_mode="none" — no internet by default, ever. The
  registry-only egress network is attached for the install phase and detached before
  tests. Attaching to a running container is a supported Docker operation; if it fails
  we RAISE so the problem is loud on the VM on day 1 (fallback design, if ever needed:
  the workbook's install→commit→fresh-none-container variant, which requires a writable
  rootfs and was rejected for containment).
- The orchestrator (trusted code) fetches the repo tarball and materializes it into
  /workspace (the writable tmpfs) — NOT /tmp, and failures raise instead of passing
  silently, with an emptiness check so an empty sandbox can't look like a successful run.
- Python dependencies install into a per-run venv on /workspace (the root filesystem is
  read-only; PATH is ordered so venv binaries win).
- behaviour() reports per-run signals only: canary values (printed OR written to files),
  denied writes from stderr, limits from exit codes, connection-error hosts from stderr.
  The shared squid access log is deliberately NOT parsed — its lines can't be attributed
  to one run. A per-run proxy container is the VM-week follow-up (T12).
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
import tarfile
import time
from typing import Literal

from app.core.config import Settings
from app.guardrails.output import DENIED_WRITE_MARKER
from app.sandbox.base import BehaviourReport, ExecResult, Phase, RepoSpec

log = logging.getLogger("airlock.sandbox.docker")

# python:3.12-slim's default PATH with the per-run venv prepended (created by the
# orchestrator's fixed `python -m venv --system-site-packages /workspace/.venv` step).
VENV_PATH = "/workspace/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


class DockerSandboxSession:
    def __init__(
        self,
        client,
        container,
        which: Literal["base", "pr"],
        settings: Settings,
        canaries: dict[str, str],
        on_destroy,
    ):
        self.which = which
        self._client = client
        self._container = container
        self._settings = settings
        self._canaries = canaries
        self._on_destroy = on_destroy
        self._outputs: list[ExecResult] = []
        self._egress_attached = False
        self._destroyed = False

    async def exec(self, command: str, *, phase: Phase, timeout_s: int) -> ExecResult:
        wrapped = f"timeout -k 5 {timeout_s} sh -c '{command}'"
        result = await asyncio.to_thread(
            self._container.exec_run,
            ["sh", "-c", wrapped],
            user="1000:1000",
            demux=True,
        )
        exit_code = int(result.exit_code or 0)
        stdout_b, stderr_b = result.output or (b"", b"")
        res = ExecResult(
            exit_code=exit_code,
            stdout=(stdout_b or b"").decode(errors="replace")[-4000:],
            stderr=(stderr_b or b"").decode(errors="replace")[-4000:],
            timed_out=exit_code in (124, 137),
            duration_ms=0,
        )
        self._outputs.append(res)  # raw, pre-redaction: behaviour() scans this
        return res

    async def write_file(self, path: str, content: str) -> None:
        escaped = content.replace("'", "'\\''")
        result = await asyncio.to_thread(
            self._container.exec_run,
            ["sh", "-c", f"mkdir -p $(dirname {path}) && printf '%s' '{escaped}' > {path}"],
            user="1000:1000",
        )
        if int(result.exit_code or 0) != 0:
            raise RuntimeError(f"write_file failed for {path}")

    async def materialize(self, tarball: bytes) -> None:
        """Unpack the repo tarball into /workspace (the writable tmpfs), loudly: upload
        errors, tar errors and an emptiness check all raise — an empty sandbox must never
        masquerade as a successful checkout."""
        wrapper = io.BytesIO()
        with tarfile.open(fileobj=wrapper, mode="w") as tf:
            info = tarfile.TarInfo(name="inject.tar")
            info.size = len(tarball)
            tf.addfile(info, io.BytesIO(tarball))
        try:
            await asyncio.to_thread(self._container.put_archive, "/workspace", wrapper.getvalue())
        except Exception as e:  # noqa: BLE001 — surfaced, never silent
            raise RuntimeError(f"put_archive into /workspace failed: {e}") from e
        res = await asyncio.to_thread(
            self._container.exec_run,
            [
                "sh",
                "-c",
                "tar -xf /workspace/inject.tar -C /workspace --strip-components=1"
                " && rm -f /workspace/inject.tar",
            ],
            user="1000:1000",
        )
        if int(res.exit_code or 0) != 0:
            stderr = (res.output[1] or b"").decode(errors="replace")[:300]
            raise RuntimeError(f"repo extraction failed inside the sandbox: {stderr}")
        check = await asyncio.to_thread(
            self._container.exec_run,
            ["sh", "-c", "test -n \"$(ls -A /workspace 2>/dev/null)\""],
            user="1000:1000",
        )
        if int(check.exit_code or 0) != 0:
            raise RuntimeError("workspace is empty after materialization")

    async def use_network(self, enable: bool) -> None:
        """Attach/detach the registry-only egress network. Containers run network-less
        outside the install phase. Attaching to a running container is supported by
        Docker even when it was started with network_mode=none — but if it fails we
        raise, so this surfaces on the VM immediately instead of quietly breaking installs."""
        try:
            network = self._client.networks.get(self._settings.egress_network)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"egress network {self._settings.egress_network} not found: {e}") from e
        try:
            if enable and not self._egress_attached:
                await asyncio.to_thread(network.connect, self._container)
                self._egress_attached = True
            elif not enable and self._egress_attached:
                await asyncio.to_thread(network.disconnect, self._container)
                self._egress_attached = False
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"could not {'attach' if enable else 'detach'} egress network: {e}") from e

    async def behaviour(self) -> BehaviourReport:
        raw = "\n".join((r.stdout or "") + (r.stderr or "") for r in self._outputs)
        canaries_seen = set(
            name for name, v in self._canaries.items() if v and v in raw
        ) | set(await self._canaries_in_files())
        fs_denied = (
            ["write outside the repo denied (read-only root)"]
            if DENIED_WRITE_MARKER.search(raw)
            else []
        )
        limits: list[str] = []
        for r in self._outputs:
            if r.timed_out and "time" not in limits:
                limits.append("time")
            if r.exit_code == 137 and "kill" not in limits:
                limits.append("memory_or_pids")
        network = sorted(set(self._hosts_from_stderr(raw)))
        return BehaviourReport(
            network_attempts=network,
            proxy_denied=[f"DENIED {h}" for h in network],
            canary_hits=sorted(canaries_seen),
            fs_denied=fs_denied,
            limits_hit=limits,
        )

    async def _canaries_in_files(self) -> list[str]:
        """Canaries that were written to disk inside the sandbox (not just printed)."""
        found: list[str] = []
        for name, value in self._canaries.items():
            if not value:
                continue
            try:
                res = await asyncio.to_thread(
                    self._container.exec_run,
                    ["sh", "-c", f"grep -rIlF -- '{value}' /workspace /tmp 2>/dev/null | head -3"],
                    user="1000:1000",
                )
                if int(res.exit_code or 0) == 0 and (res.output or b"").strip():
                    found.append(name)
            except Exception:  # noqa: BLE001 — best-effort evidence
                continue
        return found

    @staticmethod
    def _hosts_from_stderr(raw: str) -> list[str]:
        hosts: list[str] = []
        for m in re.finditer(
            r"(?:could not (?:connect|resolve)[^:\n]*[:\s])((?:\d{1,3}\.){3}\d{1,3}|[a-z0-9.\-]+\.[a-z]{2,})",
            raw,
            re.I,
        ):
            hosts.append(m.group(1))
        return hosts

    async def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        try:
            await asyncio.to_thread(self._container.remove, force=True, v=True)
        finally:
            self._on_destroy()


class DockerSandbox:
    name = "docker"
    alive = 0
    created = 0

    def __init__(self, settings: Settings):
        self._settings = settings

    def _client(self):
        import docker  # imported lazily; only available on the VM

        return docker.from_env()

    async def create(
        self, spec: RepoSpec, *, language: str, run_id: str, canaries: dict[str, str]
    ) -> DockerSandboxSession:
        client = self._client()
        s = self._settings
        image = f"airlock-sandbox-{'node' if language == 'node' else 'python'}:1"
        container = await asyncio.to_thread(
            client.containers.run,
            image,
            command=["sleep", "infinity"],
            detach=True,
            runtime=s.sandbox_runtime,  # runsc (gVisor); falls back to runc if missing
            network_mode="none",  # default-deny; egress attaches only for install
            user="1000:1000",
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            read_only=True,
            tmpfs={"/tmp": "size=256m", "/workspace": "size=1g,uid=1000"},
            mem_limit=s.sandbox_mem_limit,
            memswap_limit=s.sandbox_mem_limit,
            nano_cpus=int(s.sandbox_cpus * 1e9),
            pids_limit=s.sandbox_pids_limit,
            environment={
                # venv binaries first so `python`/`pytest` resolve into the per-run venv
                "PATH": VENV_PATH,
                **canaries,  # planted canaries only; real keys stay in the orchestrator
                "HTTP_PROXY": s.egress_proxy,
                "HTTPS_PROXY": s.egress_proxy,
            },
            labels={
                "airlock.run_id": run_id,
                "airlock.ref": spec.ref,
                "airlock.created": str(int(time.time())),
            },
        )
        DockerSandbox.created += 1
        DockerSandbox.alive += 1

        def _dec() -> None:
            DockerSandbox.alive -= 1

        return DockerSandboxSession(client, container, spec.ref, s, canaries, _dec)
