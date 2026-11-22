# Nexx Universal Swarms Gateway

An **additive, opt-in project integration layer** for the existing Apache-2.0 Swarms framework. It does not replace or modify upstream Swarms core. This is an implemented foundation and is **not** evidence of production deployment, credentials being configured, or a successful live LLM call.

## Purpose and integration architecture

Any current or future Nexx backend can call one private Swarms service using its own project credential. The backend first authenticates its end user and verifies workspace membership, tenant access, and the requested workflow. Only then does the backend forward an authorized request to the gateway. Never call the gateway directly from a public browser/mobile app.

Architecture:

1. Nexx AI, Nexx Orbit, Nexx Hotel, Nexx EventPass, Nexx Pay, Nexx Bank, Nexx Circle, WorldLife or another Nexx project (backend only)
2. Private HTTPS + project-specific Bearer token
3. Gateway project authentication, workflow allowlist, process-local rate/concurrency admission
4. Fixed bounded Swarms SequentialWorkflow agents, one loop each, no registered external tools
5. Operator-approved LLM provider

Project identity is inferred from the token, not a caller-provided project ID. The caller-supplied tenant_id is an **assertion by the trusted project backend**, NOT independently validated by the gateway; this first release does not connect to each project's identity database. Tenant membership enforcement must happen upstream. This gateway persists no conversation history or data.

## Supported workflows and suggested project scopes

- research: verified-facts planning and uncertainty review
- creative: creative brief and production instructions (does not render media)
- software: architecture and engineering review (does not push code)
- operations: operational analysis and actionable recommendations
- support: draft customer responses with privacy review
- commerce: storefront and fulfilment guidance (does not alter inventory)
- finance_readonly: advisory financial review (cannot make payments or financial decisions)

Suggested scopes: Nexx AI (research, creative, software, operations); Nexx Orbit (research, software, operations); Nexx Hotel (operations, support, commerce); EventPass (operations, support, creative); Nexx Pay and Bank (finance_readonly, support); Circle (commerce, support, creative); WorldLife (creative, software). These are suggestions, NOT automatically enabled configurations. Arbitrary new Nexx project IDs can be added without changing source code.

## Setup

Use Python 3.11+ on a trusted private worker or container. From repository root, create and activate a virtual environment, then install:

    pip install -e .
    pip install -r nexx_gateway/requirements.txt

Generate a different long cryptographically random service token per project:

    python -c "import secrets; print(secrets.token_urlsafe(48))"

Supply a secret environment variable NEXX_PROJECTS_JSON as a JSON map. Do not commit it, paste it in logs, or put it in browser code. Example with FAKE keys:

    {
      "nexx-ai": {
        "api_key": "REPLACE_WITH_UNIQUE_RANDOM_SECRET_AT_LEAST_32_CHARS",
        "model": "groq/openai/gpt-oss-20b",
        "workflows": ["research", "creative", "software"],
        "requests_per_minute": 10
      },
      "nexx-eventpass": {
        "api_key": "DIFFERENT_RANDOM_SECRET_FOR_EVENTPASS_LONG_ENOUGH",
        "model": "groq/openai/gpt-oss-20b",
        "workflows": ["operations", "support"],
        "requests_per_minute": 5
      }
    }

Set the real provider credentials (e.g. GROQ_API_KEY) only on the private runtime. A default model can be set using NEXX_DEFAULT_MODEL instead of per-project model. NEXX_MAX_CONCURRENT_RUNS defaults to 2. Each project may be disabled using enabled: false. Misconfigured or empty project registry fails closed. See nexx_gateway/.env.example.

Local run:

    uvicorn nexx_gateway.app:app --host 127.0.0.1 --port 8000

Build container from repository root:

    docker build -f nexx_gateway/Dockerfile -t nexx-swarms-gateway .

## HTTP contract

- GET /health: liveness only (not credential/provider readiness)
- GET /ready: validates registry configuration only (not live provider connection)
- GET /v1/capabilities: Bearer project token required; returns only calling project's allowed workflows
- POST /v1/runs: Bearer token required; bounded synchronous execution

Example JSON request to /v1/runs:

    {
      "tenant_id": "authorized-workspace-123",
      "workflow": "research",
      "task": "Summarize migration risks for this architecture.",
      "max_output_chars": 12000
    }

Successful response includes a generated run_id, authenticated project_id, asserted tenant_id, workflow, output, truncation flag, agent_count and elapsed_ms. A request cannot pick its own provider/model or provide an arbitrary tool. Unsupported workflows return HTTP 403. Absent or bad credentials return HTTP 401. Excessive requests return HTTP 429, process capacity HTTP 503, and sanitized execution failures HTTP 502.

Python backend integration example (requires httpx and already authorized workspace/user context):

    import os
    import httpx

    response = httpx.post(
        os.environ["NEXX_SWARMS_GATEWAY_URL"].rstrip("/") + "/v1/runs",
        headers={"Authorization": "Bearer " + os.environ["NEXX_SWARMS_PROJECT_TOKEN"]},
        json={
            "tenant_id": authorized_workspace_id,
            "workflow": "research",
            "task": user_task,
        },
        timeout=120,
    )
    response.raise_for_status()
    result = response.json()["output"]

The service-to-service token belongs in the caller backend's secret manager; never in JavaScript shipped to the browser.

## Safety and production gaps

- Synchronous execution; no durable job queue, retry, cancellation, replay protection or results database.
- RPM and concurrency limits are **in-process only**, not distributed quotas or financial spend caps. Add Redis/DB-backed admission control and provider-side hard spending limits for multi-replica production.
- Each calling backend is responsible for end-user authentication, tenant authorization, per-user quotas, consent, and safe output rendering. A project key does not prove membership in a particular tenant.
- No external tool invocation, shell, arbitrary MCP, checkout, card/account changes or automatically applied actions are available. LLM output is untrusted: require human authorization for consequential changes.
- Real provider behavior, telemetry, upstream Swarms execution characteristics and private data egress must be independently audited before handling regulated/private information.
- TLS/private network allowlisting, secret rotation, central redacted auditing, security monitoring, deployment configuration and full provider integration tests remain outstanding.

## Tests

    pip install -r nexx_gateway/requirements.txt pytest httpx
    python -m pytest -q nexx_gateway/tests

Tests inject a fake runner, so they check project credentials, workflow permissions, schema validation, rate limiting, output truncation and failure sanitization without model charges. Passing these tests is NOT live model-provider verification.
