# Flow Memory API

Flow Memory has a dependency-free internal router plus optional server seams.

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

## Auth seams

- `src/flow_memory/api/auth.py` implements local API-key checking seam.
- `src/flow_memory/api/signed_requests.py` implements signed request test seam.
- DID request signatures are a documented placeholder, not production auth.

## Optional server

`src/flow_memory/api/server.py` exposes a FastAPI server creation seam when FastAPI is installed. FastAPI is not required by the base test suite.

## Status

The internal router and OpenAPI generation are tested. Production server deployment, rate limiting, auth hardening, and public networking remain future work.
