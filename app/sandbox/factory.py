"""Composition: pick the sandbox backend from settings."""
from __future__ import annotations

from app.core.config import Settings
from app.sandbox.base import SandboxBackend
from app.sandbox.dummy import DummySandbox


def build_sandbox(settings: Settings) -> SandboxBackend:
    if settings.sandbox_backend == "docker":
        from app.sandbox.docker_backend import DockerSandbox

        return DockerSandbox(settings)  # type: ignore[return-value]
    if settings.sandbox_backend == "vultr_vm":
        from app.sandbox.vultr_vm import VultrVMSandbox

        return VultrVMSandbox(settings)  # type: ignore[return-value, abstract]
    return DummySandbox()
