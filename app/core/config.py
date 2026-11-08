"""Settings (pydantic-settings) and the prod startup check."""
from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIRLOCK_", env_file=str(REPO_ROOT / ".env"), extra="ignore"
    )

    env: str = "dev"  # dev | staging | prod

    # LLM (Vultr Serverless Inference)
    llm_provider: str = "dummy"  # dummy | vultr
    vultr_inference_base_url: str = "https://api.vultrinference.com/v1"
    vultr_inference_api_key: SecretStr = SecretStr("")
    planner_model: str = ""
    coder_model: str = ""
    llm_token_budget_per_run: int = 120_000
    llm_max_concurrent: int = 4

    # Sandbox
    sandbox_backend: str = "dummy"  # dummy | docker | vultr_vm
    sandbox_runtime: str = "runsc"
    sandbox_mem_limit: str = "1g"
    sandbox_cpus: float = 1.0
    sandbox_pids_limit: int = 128
    sandbox_install_timeout_s: int = 180
    sandbox_test_timeout_s: int = 120
    egress_proxy: str = "http://egress-proxy:3128"
    egress_network: str = "airlock-egress"

    # Storage / queue
    database_url: str = "sqlite+aiosqlite:///./airlock.db"
    db_path: str = str(REPO_ROOT / "airlock-store.db")  # write-through persistence; "" disables
    queue_backend: str = "inprocess"  # inprocess | arq
    worker_concurrency: int = 2

    # Auth / limits
    session_secret: SecretStr = SecretStr("dev-only-secret-change-me-0123456789abcdef")
    bootstrap_admin_key: str = ""
    rate_limit_runs_per_min: int = 5
    rate_limit_demo_per_min: int = 10

    # External
    github_token: SecretStr = SecretStr("")
    vultr_api_key: SecretStr = SecretStr("")

    policy_path: str = str(REPO_ROOT / "policies" / "policy_v1.yaml")


def check_prod(settings: Settings) -> None:
    """Refuse to boot prod with dev defaults."""
    problems: list[str] = []
    if settings.llm_provider == "dummy":
        problems.append("LLM provider is dummy")
    if settings.sandbox_backend == "dummy":
        problems.append("sandbox backend is dummy")
    if settings.session_secret.get_secret_value().startswith("dev-only"):
        problems.append("session secret is the dev default")
    if not settings.bootstrap_admin_key:
        problems.append("bootstrap admin key is empty")
    if not settings.planner_model:
        problems.append("planner model is not set (pick from GET /v1/models)")
    if problems:
        raise RuntimeError("refusing to boot prod with dev defaults: " + "; ".join(problems))
