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
