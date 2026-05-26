# Flow Memory API

Flow Memory has a dependency-free internal router, a dependency-free local HTTP server, and optional server seams.

## Local router

Path: `src/flow_memory/api/router.py`

Use in tests and local tools without starting a server:

```python
from flow_memory.api.router import create_default_router
router = create_default_router()
router.dispatch("GET", "/health")
```

## Endpoint groups

- `/health`
- `/agents`
- `/agents/{id}`
- `/agents/{id}/run`
- `/agents/{id}/memory`
- `/agents/{id}/skills`
- `/flowlang/compile`
- `/flowlang/validate`
- `/flowlang/run`
- `/flowlang/examples`
- `/runtime/status`
- `/runtime/tick`
- `/marketplace/tasks`
- `/marketplace/bids`
- `/marketplace/assign`
- `/marketplace/submit`
- `/marketplace/verify`
- `/marketplace/settle`
- `/marketplace/dispute`
- `/reputation/{agent_id}`
- `/attestations`
- `/audit`
- `/swarm/agents`
- `/swarm/delegate`
- `/verification/submit`
- `/verification/result`
- `/agents/launch`
- `/agents/launch-flowlang`
- `/agents/launch-neural`
- `/launch/agent`
- `/launch/agent/from-flow`
- `/network/run-scenario`
- `/cognition/predict`
- `/cognition/tick`
- `/cognition/benchmarks/run`
- `/cognition/lessons`
- `/cognition/metrics`
- `/genesis/archetypes`
- `/genesis/instincts`
- `/genesis/boundaries`
- `/genesis/birth`
- `/genesis/agents/{agent_id}/passport`
- `/genesis/agents/{agent_id}/genome`
- `/genesis/agents/{agent_id}/mirror`
- `/genesis/agents/{agent_id}/teaching`
- `/genesis/contributions`
- `/genesis/contributions/export`

## OpenAPI

`src/flow_memory/api/openapi.py` generates a local OpenAPI JSON document from the endpoint manifest.


## Snapshot validation

`src/flow_memory/api/snapshot.py` creates a deterministic API snapshot with endpoint count, operation list, path list, manifest hash, and OpenAPI hash.

Generate the committed snapshot with:

```bash
python scripts/export_api_snapshot.py --write docs/API_SNAPSHOT.json
```

Use `validate_api_snapshot()` in release checks to detect accidental endpoint drift.

## Dependency-free local HTTP server

`src/flow_memory/api/http_server.py` wraps the internal router with JSON parsing, local API-key checks, optional scope enforcement, rate limiting, audit events, and the standard API error contract.

Run it locally:

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765
```

With local preflight auth:

```bash
python scripts/run_local_api_server.py --api-key dev-local-only --require-scopes
```

## Auth seams

- `src/flow_memory/api/auth.py` implements local API-key checking seam.
- `src/flow_memory/api/signed_requests.py` implements signed request test seam.
- DID request signatures are a documented placeholder, not production auth.

## Optional FastAPI server

`src/flow_memory/api/server.py` exposes a FastAPI server creation seam when FastAPI is installed. FastAPI is not required by the base test suite.

## Status

The internal router, dependency-free HTTP server boundary, OpenAPI generation, signed request seam, API auth/scope/rate-limit checks, and API snapshot validation are tested. Production server deployment, replay protection, TLS termination, tenant isolation, and public networking remain future work.


## Flow Arena RL + Neural Evidence RC update

This repo now includes Flow Arena, a dependency-free local RL environment layer for agent-economy decision training, plus GPU evidence import/release-gate seams. RL policies are advisory only; policy, approval, autonomy, and economy risk controls remain authoritative. Neural GPU validation evidence is stored as text/JSON metadata and hashes; raw checkpoint/model artifacts are not committed.


## RL Arena endpoints

See `docs/API_RL.md` for `/rl/envs`, `/rl/benchmarks`, `/rl/evaluate`, and `/rl/train-smoke`. These endpoints are local/public-alpha seams and require `rl:*` scopes when scope enforcement is enabled.

## Agent launch endpoints

See `docs/API_AGENT_LAUNCH.md` for the local public-alpha launch endpoints. These endpoints require `agents:launch` or `network:run` when scope enforcement is enabled.

## Release evidence endpoints

The local API exposes read-only release metadata for public-alpha tooling:

- `GET /release/evidence` returns the committed release evidence bundle index metadata and never exposes raw artifacts.
- `GET /release/decision/{target}` returns local release-readiness decisions for `local`, `neural-gpu-smoke`, `public-alpha-neural`, `public-alpha-launch`, `public-alpha-launch-finalizer`, and `public-alpha-cognition`.
`public-alpha-genesis` validates Agent Genesis, Network Learning Protocol, private-only defaults, sanitized contribution records, and Mission Control genesis telemetry.

When scope checks are enabled these endpoints require `release:read`.

## Dashboard snapshot endpoint

`GET /dashboard/snapshot` returns typed mock snapshot metadata for the public-alpha dashboard scaffold, including neural/GPU evidence status, RL benchmark summaries, agent launch paths, local network scenarios, and simulated payment flows. It is mock data only and requires `dashboard:read` when scope checks are enabled.

### Live Agent Operations

- `GET /launch/runs`
- `GET /launch/runs/{run_id}`
- `POST /launch/runs/{run_id}/replay`
- `POST /launch/runs/{run_id}/export`
- `POST /launch/runs/{run_id}/stop`

These operate on local launch run metadata and replay artifacts only.

## Live Agent Supervisor endpoints

- `POST /launch/supervisor/start`
- `GET /launch/supervisor/status`
- `GET /launch/supervisor/runs/{run_id}`
- `GET /launch/supervisor/runs/{run_id}/heartbeat`
- `POST /launch/supervisor/runs/{run_id}/pause`
- `POST /launch/supervisor/runs/{run_id}/resume`
- `POST /launch/supervisor/runs/{run_id}/stop`

These endpoints expose local supervisor metadata and heartbeat artifacts only. They remain bounded, local-only, and policy-gated.

## Mission Control run console and demo bundle endpoints

- `GET /launch/console/runs`
- `GET /launch/console/runs/{run_id}`
- `GET /launch/console/fixtures`
- `POST /launch/bundles/public-alpha`
- `POST /launch/finalize/public-alpha`

Console read endpoints require `launch:read`; demo bundle and finalizer exports require `launch:export` when scope checks are enabled. They expose local replay/run metadata, a compact public-alpha bundle with fixture references, docs references, commands, release evidence summary, GPU evidence status, Mission Control Live 3D Mode readiness, final release decisions, and honest limitations.

## Predictive cognition endpoints

- `POST /cognition/predict`
- `POST /cognition/tick`
- `GET /cognition/experiences`
- `GET /cognition/experiences/{experience_id}`
- `GET /cognition/prediction-errors`
- `POST /cognition/memory/query`
- `POST /cognition/benchmarks/run`
- `GET /cognition/benchmarks`
- `GET /cognition/benchmarks/{benchmark_id}`
- `POST /cognition/lessons/consolidate`
- `GET /cognition/lessons`
- `GET /cognition/lessons/{lesson_id}`
- `GET /cognition/metrics`

Prediction reads require `cognition:read`; bounded ticks and benchmark runs require `cognition:run cognition:write`; lesson consolidation requires `cognition:write`. These endpoints are local public-alpha seams for deterministic predictive cognition, lesson consolidation, and benchmark metrics. They do not authorize actions or bypass PolicyEngine/ApprovalGate.

## Agent Genesis endpoints

These endpoints support no-download first-agent creation, Agent Genome inspection, private Memory Seed flow, Agent Mirror, Agent Passport, human teaching events, and opt-in network learning contribution records.

```text
GET /genesis/archetypes
GET /genesis/instincts
GET /genesis/boundaries
POST /genesis/birth
GET /genesis/agents/{agent_id}/passport
GET /genesis/agents/{agent_id}/genome
GET /genesis/agents/{agent_id}/mirror
POST /genesis/agents/{agent_id}/teaching
GET /genesis/contributions
POST /genesis/contributions/export
```

Scope mapping:

- `genesis:read` for read endpoints.
- `genesis:create` for birth.
- `genesis:teach` for teaching events.
- `genesis:export` for contribution export.

Raw private payloads are excluded by default. Network learning stays private only unless an explicit consent mode allows sanitized records.
