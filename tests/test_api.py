"""API tests via TestClient: health, demo run end-to-end, auth, owner isolation."""
import time

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_and_ready():
    with TestClient(create_app()) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        ready = client.get("/readyz").json()
        assert ready["llm"] == "dummy"
        assert ready["sandbox"] == "dummy"
        assert ready["policy_version"]


def test_demo_run_end_to_end():
    with TestClient(create_app()) as client:
        resp = client.post("/v1/demo/runs", json={"scenario": "malicious"})
        assert resp.status_code == 202
        run_id = resp.json()["id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            out = client.get(f"/v1/runs/{run_id}").json()
            if out["status"] in ("completed", "failed"):
                break
            time.sleep(0.2)
        assert out["status"] == "completed"
        assert out["verdict"]["label"] == "suspicious"
        categories = {f["category"] for f in out["findings"]}
        assert {"network_attempt", "secret_access"} <= categories
        assert out["counters"]["network_blocked"] >= 1


def test_runs_require_api_key():
    with TestClient(create_app()) as client:
        assert client.post("/v1/runs", json={"pr_url": "https://github.com/o/r/pull/1"}).status_code == 401
        assert (
            client.post(
                "/v1/runs",
                json={"pr_url": "https://github.com/o/r/pull/1"},
                headers={"X-API-Key": "wrong"},
            ).status_code
            == 401
        )


def test_invalid_pr_url_is_422():
    with TestClient(create_app()) as client:
        key = client.app.state.services.dev_admin_key
        resp = client.post(
            "/v1/runs", json={"pr_url": "https://gitlab.com/o/r/pull/1"}, headers={"X-API-Key": key}
        )
        assert resp.status_code == 422
        assert resp.json()["error"] == "invalid_pr_url"


def test_owner_isolation_returns_404():
    with TestClient(create_app()) as client:
        key = client.app.state.services.dev_admin_key
        resp = client.post(
            "/v1/runs", json={"pr_url": "https://github.com/0xv3nm09/clean-lib/pull/1"}, headers={"X-API-Key": key}
        )
        assert resp.status_code == 202
        run_id = resp.json()["id"]
        # anonymous callers get 404 (not 403) so run IDs don't leak
        assert client.get(f"/v1/runs/{run_id}").status_code == 404
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            out = client.get(f"/v1/runs/{run_id}", headers={"X-API-Key": key}).json()
            if out["status"] in ("completed", "failed"):
                break
            time.sleep(0.2)
        assert out["status"] == "completed"
        assert out["verdict"]["label"] == "safe_to_merge"


def test_trace_endpoint_replays_events():
    with TestClient(create_app()) as client:
        resp = client.post("/v1/demo/runs", json={"scenario": "clean"})
        run_id = resp.json()["id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if client.get(f"/v1/runs/{run_id}").json()["status"] == "completed":
                break
            time.sleep(0.2)
        trace = client.get(f"/v1/runs/{run_id}/trace").json()
        assert len(trace) > 10
        assert trace[0]["type"] == "status" and trace[0]["name"] == "running"
        assert trace[-1]["name"] == "completed"
        seqs = [e["seq"] for e in trace]
        assert seqs == sorted(seqs)


def test_review_decision_flow():
    with TestClient(create_app()) as client:
        key = client.app.state.services.dev_admin_key
        run_id = client.post("/v1/demo/runs", json={"scenario": "malicious"}).json()["id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if client.get(f"/v1/runs/{run_id}").json()["status"] == "completed":
                break
            time.sleep(0.2)
        # decision requires the runs:approve scope
        assert (
            client.post(f"/v1/runs/{run_id}/decision", json={"decision": "rejected"}).status_code
            == 401
        )
        resp = client.post(
            f"/v1/runs/{run_id}/decision",
            json={"decision": "rejected", "note": "confirmed canary theft"},
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 200
        out = resp.json()
        assert out["human_decision"] == "rejected"
        assert out["decided_by"] == "admin"
        assert out["human_note"] == "confirmed canary theft"
        # admin sees all runs in the list (review queue source)
        listed = client.get("/v1/runs", headers={"X-API-Key": key}).json()
        assert any(r["id"] == run_id for r in listed)


def test_session_cookie_unlocks_sse_for_owner_runs():
    """EventSource cannot send headers — the cookie session must carry the auth."""
    with TestClient(create_app()) as client:
        key = client.app.state.services.dev_admin_key
        # bad key rejected
        bad = client.post("/v1/auth/session", json={"api_key": "wrong-key-123456"})
        assert bad.status_code == 401
        resp = client.post("/v1/auth/session", json={"api_key": key})
        assert resp.status_code == 200
        assert "airlock_session" in resp.cookies
        run_id = client.post(
            "/v1/runs",
            json={"pr_url": "https://github.com/0xv3nm09/clean-lib/pull/1"},
            headers={"X-API-Key": key},
        ).json()["id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if client.get(f"/v1/runs/{run_id}").json()["status"] == "completed":
                break
            time.sleep(0.2)
        # cookie only — no X-API-Key header — must be able to read the run AND its stream
        assert client.get(f"/v1/runs/{run_id}").status_code == 200
        stream = client.get(f"/v1/runs/{run_id}/events")  # TestClient shares the cookie jar
        assert stream.status_code == 200
        assert '"name":"completed"' in stream.text


def test_usage_is_persisted():
    with TestClient(create_app()) as client:
        run_id = client.post("/v1/demo/runs", json={"scenario": "clean"}).json()["id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            out = client.get(f"/v1/runs/{run_id}").json()
            if out["status"] == "completed":
                break
            time.sleep(0.2)
        assert out["usage"]["llm_calls"] > 0
        assert out["usage"]["prompt_tokens"] > 0


def test_finding_events_carry_evidence():
    with TestClient(create_app()) as client:
        run_id = client.post("/v1/demo/runs", json={"scenario": "malicious"}).json()["id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if client.get(f"/v1/runs/{run_id}").json()["status"] == "completed":
                break
            time.sleep(0.2)
        trace = client.get(f"/v1/runs/{run_id}/trace").json()
        finding_events = [e for e in trace if e["type"] == "finding"]
        assert finding_events, "malicious run must raise findings"
        assert any(e["data"].get("evidence") for e in finding_events), (
            "receipt drawers read evidence from the live events"
        )


def test_cancelled_before_start_is_not_stuck_queued():
    with TestClient(create_app()) as client:
        key = client.app.state.services.dev_admin_key
        run_id = client.post(
            "/v1/runs",
            json={"pr_url": "https://github.com/0xv3nm09/clean-lib/pull/1"},
            headers={"X-API-Key": key},
        ).json()["id"]
        client.post(f"/v1/runs/{run_id}/cancel", headers={"X-API-Key": key})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = client.get(f"/v1/runs/{run_id}", headers={"X-API-Key": key}).json()["status"]
            if status == "cancelled":
                break
            time.sleep(0.1)
        assert status == "cancelled"


def test_public_stats_and_recent_feed():
    with TestClient(create_app()) as client:
        run_id = client.post("/v1/demo/runs", json={"scenario": "malicious"}).json()["id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if client.get(f"/v1/runs/{run_id}").json()["status"] == "completed":
                break
            time.sleep(0.2)
        stats = client.get("/v1/stats").json()
        assert stats["runs_total"] >= 1
        assert stats["suspicious"] >= 1
        assert stats["attacks_contained"] >= 1
        assert stats["tokens_total"] > 0
        assert stats["llm"]
        recent = client.get("/v1/runs/recent").json()
        assert any(r["id"] == run_id for r in recent), "demo runs appear in the public feed"
        entry = next(r for r in recent if r["id"] == run_id)
        assert entry["verdict"] == "suspicious"
        assert entry["containment"], "containment feed lines come from real events"
        # an owner run must NOT leak into the public feed
        key = client.app.state.services.dev_admin_key
        own_id = client.post(
            "/v1/runs",
            json={"pr_url": "https://github.com/0xv3nm09/clean-lib/pull/1"},
            headers={"X-API-Key": key},
        ).json()["id"]
        recent_ids = {r["id"] for r in client.get("/v1/runs/recent").json()}
        assert own_id not in recent_ids
        # but its totals do feed the aggregate counters (numbers only, no pr_url)
        stats2 = client.get("/v1/stats").json()
        assert stats2["runs_total"] >= 2


def test_demo_rate_limit_ignores_spoofed_first_hop():
    """A client-supplied first XFF hop must not reset the limit; only the LAST hop —
    the one our own proxy appended — keys the limiter."""
    with TestClient(create_app()) as client:
        codes = []
        for i in range(12):
            r = client.post(
                "/v1/demo/runs",
                json={"scenario": "clean"},
                headers={"X-Forwarded-For": f"1.2.3.{i}, 9.9.9.9"},
            )
            codes.append(r.status_code)
        assert 429 in codes, "same last hop must share one limit bucket"


def test_verdict_event_carries_summary_and_reasons():
    with TestClient(create_app()) as client:
        run_id = client.post("/v1/demo/runs", json={"scenario": "malicious"}).json()["id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if client.get(f"/v1/runs/{run_id}").json()["status"] == "completed":
                break
            time.sleep(0.2)
        trace = client.get(f"/v1/runs/{run_id}/trace").json()
        verdict = next(e for e in trace if e["type"] == "verdict")
        assert verdict["data"].get("summary"), "live verdict must carry the summary"
        assert verdict["data"].get("reasons"), "live verdict must carry the reasons"


def test_benchmark_cases_are_openable_as_live_runs():
    """Every library case can be run live (public, demo-scope) and then opened at /runs/{id}
    with verdict, receipts and token usage."""
    with TestClient(create_app()) as client:
        cases = client.get("/v1/benchmark/cases").json()
        assert len(cases) == 19
        assert {c["name"] for c in cases} >= {"clean-lib", "setup-py-exfil", "install-broken"}
        resp = client.post("/v1/benchmark/run/setup-py-exfil")
        assert resp.status_code == 202
        run_id = resp.json()["id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            out = client.get(f"/v1/runs/{run_id}").json()
            if out["status"] == "completed":
                break
            time.sleep(0.2)
        assert out["verdict"]["label"] == "suspicious"
        assert out["usage"]["llm_calls"] > 0
        assert out["usage"]["prompt_tokens"] > 0
        trace = client.get(f"/v1/runs/{run_id}/trace").json()
        assert len(trace) > 10  # full event log behind the run
        # unknown case rejected
        assert client.post("/v1/benchmark/run/nope").status_code == 404


def test_team_api_key_lifecycle():
    """Team keys — create (admin) → use (owner-scoped) → isolate → revoke."""
    with TestClient(create_app()) as client:
        admin_key = client.app.state.services.dev_admin_key
        # create a key for a team
        created = client.post(
            "/v1/admin/keys",
            json={"owner_id": "team-alpha"},
            headers={"X-API-Key": admin_key},
        )
        assert created.status_code == 201
        body = created.json()
        assert body["key"].startswith("ak_") and "." in body["key"]
        assert body["scopes"] == ["runs:read", "runs:write"]
        # the team key can create runs under its own owner
        resp = client.post(
            "/v1/runs",
            json={"pr_url": "https://github.com/0xv3nm09/clean-lib/pull/1"},
            headers={"X-API-Key": body["key"]},
        )
        assert resp.status_code == 202
        assert resp.json()["owner_id"] == "team-alpha"
        # owner isolation: the team key cannot see admin's runs
        own = client.get("/v1/runs", headers={"X-API-Key": body["key"]}).json()
        assert all(r["owner_id"] == "team-alpha" for r in own)
        # admin scope is never grantable
        denied = client.post(
            "/v1/admin/keys",
            json={"owner_id": "evil", "scopes": ["runs:approve", "runs:read", "runs:write"]},
            headers={"X-API-Key": admin_key},
        )
        assert "admin" not in denied.json()["scopes"]
        # a read-only key cannot start runs
        ro = client.post(
            "/v1/admin/keys",
            json={"owner_id": "auditor", "scopes": ["runs:read"]},
            headers={"X-API-Key": admin_key},
        ).json()
        assert (
            client.post(
                "/v1/runs",
                json={"pr_url": "https://github.com/0xv3nm09/clean-lib/pull/1"},
                headers={"X-API-Key": ro["key"]},
            ).status_code
            == 403
        )
        # revoke → the key stops working
        assert (
            client.post(
                f"/v1/admin/keys/{body['key_id']}/revoke", headers={"X-API-Key": admin_key}
            ).status_code
            == 200
        )
        assert (
            client.get("/v1/runs", headers={"X-API-Key": body["key"]}).status_code == 401
        )
        # non-admin callers cannot mint keys
        assert client.post("/v1/admin/keys", json={"owner_id": "x"}).status_code == 401


def test_seed_library_enqueues_all_cases():
    """One-click Dashboard fill: seed-library enqueues the whole 19-case library."""
    with TestClient(create_app()) as client:
        resp = client.post("/v1/demo/seed-library")
        assert resp.status_code == 202
        body = resp.json()
        assert body["enqueued"] == 19
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            done = sum(
                1
                for rid in body["run_ids"]
                if client.get(f"/v1/runs/{rid}").json()["status"] == "completed"
            )
            if done == 19:
                break
            time.sleep(0.3)
        assert done == 19, "all library runs must complete"
        recent = client.get("/v1/runs/recent?limit=25").json()
        recent_ids = {r["id"] for r in recent}
        assert set(body["run_ids"]) <= recent_ids, "every seeded run appears in the feed"
        assert len(recent) >= 19  # session-shared store may hold runs from earlier tests
