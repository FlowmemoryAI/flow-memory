# Safety

Status: functional local safety layer; not hardened production isolation.

## Implemented

- `OPAPolicyEngine`-compatible local Python policy boundary.
- `HumanApprovalGate` with explicit allow/deny/defer outcomes.
- `ImmutableAuditLog` hash chain.
- `RateLimiter`.
- `CircuitBreaker` wired into repeated denied/failed actions.
- Local Python sandbox with AST checks and subprocess timeout.
- Skill runner and memory graph integrate with safety/policy gates.

## Hard boundary

The sandbox is not a secure multi-tenant boundary. It is useful for local tests and benign code but must be replaced or wrapped by container/microVM isolation before untrusted code execution.

## Required before production

- Canonical policy source across Python and Rego/OPA.
- Container/microVM isolation.
- Persistent audit export/anchoring.
- Approval workflow UI/API.
- Incident response and operator runbook.
