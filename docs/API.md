# API

Status: dependency-free internal router plus optional FastAPI boundary.

Flow Memory v2 exposes a local API surface designed to grow into a larger protocol without creating hundreds of empty endpoints.

## Internal router

`src/flow_memory/api/router.py` implements `LocalApiRouter` with method/path dispatch and path parameters. It runs in process and does not launch a server.

## Endpoint groups

- `GET /health`
- `GET /runtime/status`
- `POST /runtime/tick`
- `GET /agents`
- `GET /agents/{did}`
- `GET /agents/{did}/memory`
- `GET /agents/{did}/skills`
- `POST /agents/{did}/run`
- `POST /marketplace/tasks`
- `POST /marketplace/bids`
- `POST /marketplace/settle`
- `GET /reputation/{did}`
- `POST /attestations`
- `GET /audit`
- `GET /swarm/agents`
- `POST /swarm/delegate`
- `POST /verification/submit`
- `GET /verification/result`
- `GET /manifest`

## Manifest

`src/flow_memory/api/manifest.py` exposes a machine-readable endpoint manifest.

## OpenAPI

`src/flow_memory/api/openapi.py` can generate a minimal OpenAPI-like document from the manifest. If FastAPI is installed, `create_app()` returns a tiny ASGI app for `/health` and `/manifest`; otherwise it returns the local router.

## Boundary

This is not a production API server. Authentication, authorization, replay protection, rate limiting, persistence, and external service integration remain future work.
