"""Persistence across restarts: runs, findings, events and API keys must survive the
backend process dying and coming back — the permanent fix for "data vanishes"."""
import time

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_runs_survive_a_backend_restart(tmp_path):
    db = str(tmp_path / "store.db")
    with TestClient(create_app(Settings(db_path=db))) as client:
        run_id = client.post("/v1/demo/runs", json={"scenario": "malicious"}).json()["id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            out = client.get(f"/v1/runs/{run_id}").json()
            if out["status"] == "completed":
                break
            time.sleep(0.2)
        tokens_before = out["usage"]["prompt_tokens"] + out["usage"]["completion_tokens"]

    # process "dies" and a brand-new app opens the same store file
    with TestClient(create_app(Settings(db_path=db))) as client:
        out = client.get(f"/v1/runs/{run_id}").json()
        assert out["status"] == "completed"
        assert out["verdict"]["label"] == "suspicious"
        assert out["verdict"]["summary"], "reporter summary must survive"
        assert len(out["findings"]) == 2
        assert out["usage"]["prompt_tokens"] + out["usage"]["completion_tokens"] == tokens_before
        trace = client.get(f"/v1/runs/{run_id}/trace").json()
        assert len(trace) > 10, "the full event trace must survive too"


def test_api_keys_survive_a_backend_restart(tmp_path):
    db = str(tmp_path / "store.db")
    with TestClient(create_app(Settings(db_path=db))) as client:
        admin = client.app.state.services.dev_admin_key
        key = client.post(
            "/v1/admin/keys", json={"owner_id": "team-alpha"}, headers={"X-API-Key": admin}
        ).json()

    with TestClient(create_app(Settings(db_path=db))) as client:
        admin = client.app.state.services.dev_admin_key  # stable dev key
        resp = client.get("/v1/runs", headers={"X-API-Key": key["key"]})
        assert resp.status_code == 200, "team key must still authenticate after restart"
        listed = client.get("/v1/admin/keys", headers={"X-API-Key": admin}).json()
        assert any(k["key_id"] == key["key_id"] for k in listed)


def test_persistence_can_be_disabled(tmp_path):
    db = ""  # disabled: no store file may be written anywhere
    with TestClient(create_app(Settings(db_path=db))) as client:
        client.post("/v1/demo/runs", json={"scenario": "clean"})
    assert list(tmp_path.iterdir()) == [], "empty db_path must disable persistence"
