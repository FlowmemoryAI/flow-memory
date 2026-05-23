# API Server Seam

Status: local router plus optional FastAPI seam; not a hardened public server.

## Purpose

Define the boundary between Flow Memory's in-process API manifest/router and any future network-facing service. The seam keeps endpoint shape, handler dispatch, and generated OpenAPI-like metadata testable without requiring a daemon, reverse proxy, database, or cloud service.

## Local-safe behavior

- Default execution stays in process through the dependency-light router.
- The endpoint manifest is the source of truth for route groups and handler names.
- Optional FastAPI wiring may expose health and manifest routes when the dependency is installed.
- Local handlers should use deterministic state, explicit inputs, and no hidden network calls.
- Value-bearing or externally visible operations must remain behind policy, approval, audit, and adapter boundaries.

## Auth seam

- `src/flow_memory/api/auth.py` supports local API-key checks and an explicit signed-request decision helper.
- Header matching is case-insensitive for `x-flow-memory-api-key`.
- Signed requests use the local development signing seam and verify method, path, and payload binding.
- This is test coverage for the API boundary contract, not production authentication, replay protection, tenant isolation, or key custody.


## Limitations

- Not production-authenticated or internet-facing.
- API-key and signed-request helpers are local seams only; there is no production authorization model, session handling, replay protection, tenant isolation, rate-limit enforcement at the HTTP edge, or production observability.
- Optional FastAPI support is an application seam, not a deployment architecture.
- Endpoint presence does not imply that downstream blockchain, MCP/A2A, libp2p, Redis, Qdrant, Neo4j, or OPA integrations are implemented.

## Next implementation steps

1. Promote the manifest into generated OpenAPI with stable request/response schemas.
2. Add authentication, authorization, replay protection, rate limits, and structured audit events at the server boundary.
3. Bind each network route to explicit capability checks before handler execution.
4. Add integration tests for HTTP behavior once the server contract is stable.
5. Document deployment profiles separately for local development, private lab use, and audited production use.
