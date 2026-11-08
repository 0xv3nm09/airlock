"""Throwaway Vultr VM per run — the stretch isolation boundary.

Plan: POST /v2/instances with a prepared snapshot + cloud-init user_data, DELETE in finally,
janitor tags every instance `airlock`. Vultr API v2 allows ~20 req/s (verified Oct 27) —
throttle creation loops and handle 503/429. Boot takes minutes, so keep 1-2 warm spares.
Not needed for the hackathon MVP unless the team is ahead on Nov 6-7.
"""
from __future__ import annotations


class VultrVMSandbox:
    name = "vultr_vm"

    def __init__(self, *args, **kwargs):
        raise NotImplementedError("VM-per-run is a stretch goal; implement on the VM")
