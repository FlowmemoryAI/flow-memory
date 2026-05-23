# API Auth Seams

Flow Memory public-alpha auth is a local, dependency-free seam. It is intended for deterministic tests, local tools, and preflight checks; it is not production authentication hardening.

## API key and signed request seam

`src/flow_memory/api/auth.py` provides:

- `ApiAuthConfig(api_key=..., require_signed_requests=...)`
- `require_api_key(headers, config)` using the `x-flow-memory-api-key` header
- `authorize_request(...)` combining API-key and local signed-request checks

Signed requests use the local crypto seam in `src/flow_memory/api/signed_requests.py`. Do not treat these helpers as a deployed DID authentication system.

## Request context

`src/flow_memory/api/request_context.py` normalizes request metadata without starting a network server:

- method is uppercased
- path is normalized to a leading slash
- `x-request-id`, `x-flow-memory-principal`, and `x-flow-memory-client` are read case-insensitively when present
- absent principal/client values default to `anonymous` and `local`

The context record is JSON-serializable and suitable for local audit/rate-limit tests.

## Scopes

`src/flow_memory/api/scopes.py` defines the public-alpha scope names:

- `api:read`
- `api:write`
- `api:audit`
- `api:admin`

Scopes are supplied locally with `x-flow-memory-scopes`. Commas and spaces are both accepted. Unknown scopes fail closed with `auth.invalid_scope`. Missing required scopes fail with `auth.forbidden`. `api:admin` satisfies other required scopes for local preflight only.

## Rate limit seam

`src/flow_memory/api/rate_limits.py` provides an in-memory fixed-window limiter. Callers pass `now` explicitly so tests are deterministic and no network or background clock is required.

This is not distributed enforcement. It does not persist counters and must not be described as production rate limiting.

## Audit middleware seam

`src/flow_memory/api/audit_middleware.py` wraps local handlers and records method, path, principal, request ID, status, success flag, and error code into an in-memory sink. It performs no network I/O and does not emit to external telemetry.
