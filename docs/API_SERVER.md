# API Server Seam

Status: dependency-free local HTTP server plus internal router and optional FastAPI seam; not a hardened public server.

## Purpose

Define the boundary between Flow Memory's in-process API manifest/router and any future network-facing service. The local HTTP server gives operators a concrete public-alpha loop for health checks, scoped local API calls, JSON error contracts, request audit events, and fixed-window rate-limit testing without adding FastAPI or cloud infrastructure to the base install.

## Local HTTP server

Run the dependency-free local server:

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765
```

With a local development API key and scope checks:

```bash
python scripts/run_local_api_server.py --api-key dev-local-only --require-scopes
```

Example request:

```bash
python - <<'PY'
import json, urllib.request
req = urllib.request.Request(
    'http://127.0.0.1:8765/health',
    headers={'x-flow-memory-api-key': 'dev-local-only', 'x-flow-memory-scopes': 'api:read'},
)
print(json.dumps(json.load(urllib.request.urlopen(req)), indent=2))
PY
```

## Local-safe behavior

- Default execution can stay in process through `LocalApiRouter`.
- `HttpApiGateway` wraps the router with JSON parsing, error contracts, optional API-key checks, optional scope enforcement, fixed-window local rate limiting, and audit events.
- The endpoint manifest is still the source of truth for route groups and handler names.
- Optional FastAPI wiring remains a separate application seam when the dependency is installed.
- Value-bearing or externally visible operations must remain behind policy, approval, audit, and adapter boundaries.

## Auth seam

- `src/flow_memory/api/auth.py` supports local API-key checks and an explicit signed-request decision helper.
- Header matching is case-insensitive for `x-flow-memory-api-key`.
- `src/flow_memory/api/http_server.py` enforces local API-key and scope decisions when configured.
- Signed requests use the local development signing seam and verify method, path, and payload binding.
- This is test coverage for the API boundary contract, not production authentication, replay protection, tenant isolation, or key custody.

## Limitations

- Not production-authenticated or internet-facing.
- API-key and signed-request helpers are local seams only; there is no production authorization model, session handling, replay protection, tenant isolation, distributed rate limiting, TLS termination, WAF, or production observability.
- Optional FastAPI support is an application seam, not a deployment architecture.
- Endpoint presence does not imply that downstream blockchain, MCP/A2A, libp2p, Redis, Qdrant, Neo4j, or OPA integrations are implemented.

## Next implementation steps

1. Add stable request/response schema objects per endpoint.
2. Add request signing/replay windows at the HTTP boundary.
3. Add TLS/reverse-proxy deployment profiles.
4. Add production observability hooks and structured access logs.
5. Document deployment profiles separately for local development, private lab use, and audited production use.


## Flow Arena RL + Neural Evidence RC update

This repo now includes Flow Arena, a dependency-free local RL environment layer for agent-economy decision training, plus GPU evidence import/release-gate seams. RL policies are advisory only; policy, approval, autonomy, and economy risk controls remain authoritative. Neural GPU validation evidence is stored as text/JSON metadata and hashes; raw checkpoint/model artifacts are not committed.
