"""Private project-to-project HTTP gateway for bounded Swarms workloads.

This is NOT a browser-facing endpoint. Caller backends MUST validate the user,
workspace and tenant membership before submitting tenant_id and task text.
"""

from __future__ import annotations

import re
import time
import uuid
from threading import Lock
from typing import Callable

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .config import ConfigurationError, GatewayConfig, Project, load_config
from .guard import ExecutionGuard, TooManyConcurrentRuns, TooManyRequests
from .runner import run_workflow
from .workflows import WORKFLOWS

TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=1, max_length=128, pattern=TENANT_ID_PATTERN.pattern)
    workflow: str = Field(min_length=1, max_length=64)
    task: str = Field(min_length=3, max_length=4000)
    max_output_chars: int = Field(default=12000, ge=500, le=20000)


class RunResponse(BaseModel):
    run_id: str
    project_id: str
    tenant_id: str
    workflow: str
    output: str
    truncated: bool
    agent_count: int
    elapsed_ms: int


def create_app(
    config: GatewayConfig | None = None,
    runner: Callable[[Project, str, str], str] = run_workflow,
) -> FastAPI:
    app = FastAPI(
        title="Nexx Swarms Gateway",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    cached_config: GatewayConfig | None = config
    guard: ExecutionGuard | None = None
    setup_lock = Lock()

    def configured() -> tuple[GatewayConfig, ExecutionGuard]:
        nonlocal cached_config, guard
        with setup_lock:
            if cached_config is None:
                try:
                    cached_config = load_config()
                except ConfigurationError:
                    raise HTTPException(status_code=503, detail="Service not configured") from None
            if guard is None:
                guard = ExecutionGuard(cached_config.max_concurrent_runs)
            return cached_config, guard

    def authorized_project(authorization: str | None) -> tuple[Project, ExecutionGuard]:
        cfg, admission = configured()
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Bearer"})
        token = authorization.removeprefix("Bearer ")
        if not token or len(token) > 256:
            raise HTTPException(status_code=401, detail="Unauthorized")
        project = cfg.authenticate(token)
        if project is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return project, admission

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "up"}

    @app.get("/ready")
    def readiness() -> dict[str, str]:
        configured()
        return {"status": "configured"}  # Does not prove model-provider connectivity.

    @app.get("/v1/capabilities")
    def capabilities(authorization: str | None = Header(default=None)) -> dict:
        project, _ = authorized_project(authorization)
        return {
            "project_id": project.identifier,
            "workflows": sorted(project.workflows),
            "max_task_chars": 4000,
            "external_actions_enabled": False,
        }

    @app.post("/v1/runs", response_model=RunResponse)
    def runs(payload: RunRequest, authorization: str | None = Header(default=None)) -> RunResponse:
        project, admission = authorized_project(authorization)
        if payload.workflow not in project.workflows:
            raise HTTPException(status_code=403, detail="Workflow not permitted for project")
        try:
            admission.acquire(project)
        except TooManyRequests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "60"}) from None
        except TooManyConcurrentRuns:
            raise HTTPException(status_code=503, detail="Worker capacity reached", headers={"Retry-After": "3"}) from None
        start = time.monotonic()
        run_id = str(uuid.uuid4())
        try:
            # In this MVP neither task text nor output is persisted by the gateway.
            output = runner(project, payload.workflow, payload.task)
            if not isinstance(output, str):
                raise TypeError("Runner must return a string")
        except Exception:
            # Never echo provider errors, stack traces, credentials, or task contents.
            raise HTTPException(status_code=502, detail="Agent workflow failed") from None
        finally:
            admission.release()
        return RunResponse(
            run_id=run_id,
            project_id=project.identifier,
            tenant_id=payload.tenant_id,
            workflow=payload.workflow,
            output=output[: payload.max_output_chars],
            truncated=len(output) > payload.max_output_chars,
            agent_count=len(WORKFLOWS[payload.workflow]),
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )

    return app


app = create_app()
