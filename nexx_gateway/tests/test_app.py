import json

from fastapi.testclient import TestClient

from nexx_gateway.app import create_app
from nexx_gateway.config import load_config
from nexx_gateway.guard import ExecutionGuard, TooManyRequests


def make_client(runner=None, rate=10):
    cfg = load_config({
        "NEXX_DEFAULT_MODEL": "test/model",
        "NEXX_PROJECTS_JSON": json.dumps({
            "nexx-ai": {"api_key": "a" * 48, "workflows": ["research", "software"], "requests_per_minute": rate},
            "nexx-eventpass": {"api_key": "b" * 48, "workflows": ["support"], "requests_per_minute": rate},
        }),
    })
    if runner is None:
        runner = lambda project, workflow, task: f"{project.identifier}:{workflow}:{task}"
    return TestClient(create_app(config=cfg, runner=runner))


def headers(key="a"):
    return {"Authorization": f"Bearer {key * 48}"}


def payload(**changes):
    return {"tenant_id": "tenant-1", "workflow": "research", "task": "Review the architecture", **changes}


def test_health_is_not_auth_or_provider_ready_claim():
    with make_client() as client:
        assert client.get("/health").json() == {"status": "up"}
        assert client.get("/ready").json() == {"status": "configured"}


def test_no_auth_invalid_key_or_leakage():
    with make_client() as client:
        assert client.get("/v1/capabilities").status_code == 401
        assert client.get("/v1/capabilities", headers=headers("x")).status_code == 401
        assert client.get("/v1/capabilities", headers=headers("b")).json()["workflows"] == ["support"]
        assert client.get("/v1/capabilities", headers=headers()).json()["workflows"] == ["research", "software"]


def test_cross_project_workflow_access_denied():
    with make_client() as client:
        response = client.post("/v1/runs", headers=headers("b"), json=payload())
        assert response.status_code == 403
        response = client.post("/v1/runs", headers=headers("a"), json=payload(workflow="support"))
        assert response.status_code == 403


def test_success_scopes_and_truncates():
    with make_client(runner=lambda *args: "z" * 900) as client:
        response = client.post("/v1/runs", headers=headers(), json=payload(max_output_chars=500))
        assert response.status_code == 200
        record = response.json()
        assert record["project_id"] == "nexx-ai"
        assert record["tenant_id"] == "tenant-1"
        assert record["agent_count"] == 2
        assert record["truncated"] is True
        assert len(record["output"]) == 500
        assert record["run_id"]


def test_invalid_fields_and_extra_payload_rejected():
    with make_client() as client:
        assert client.post("/v1/runs", headers=headers(), json=payload(tenant_id="../other")).status_code == 422
        assert client.post("/v1/runs", headers=headers(), json=payload(task="x")).status_code == 422
        assert client.post("/v1/runs", headers=headers(), json=payload(model="attacker/model")).status_code == 422


def test_rate_limits_by_project():
    with make_client(rate=1) as client:
        assert client.post("/v1/runs", headers=headers(), json=payload()).status_code == 200
        assert client.post("/v1/runs", headers=headers(), json=payload()).status_code == 429
        assert client.post("/v1/runs", headers=headers("b"), json=payload(workflow="support")).status_code == 200


def test_errors_do_not_expose_provider_secrets():
    def runner(*args):
        raise RuntimeError("sensitive-api-key-123")
    with make_client(runner=runner) as client:
        resp = client.post("/v1/runs", headers=headers(), json=payload())
        assert resp.status_code == 502
        assert "sensitive-api-key" not in resp.text


def test_guard_releases_capacity_and_window_rolls():
    tick = [0.0]
    cfg = load_config({"NEXX_DEFAULT_MODEL": "test/model", "NEXX_PROJECTS_JSON": json.dumps({
        "nexx-ai": {"api_key": "a" * 48, "workflows": ["research"], "requests_per_minute": 1},
    })})
    guard = ExecutionGuard(1, clock=lambda: tick[0])
    guard.acquire(cfg.projects[0])
    try:
        try:
            guard.acquire(cfg.projects[0])
            assert False
        except TooManyRequests:
            pass
    finally:
        guard.release()
    tick[0] = 61
    guard.acquire(cfg.projects[0])
    guard.release()
