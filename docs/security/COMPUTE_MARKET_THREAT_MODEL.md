# Flow Memory Compute Market Threat Model

Scope: production-planning mode for compute planning, quote normalization, route selection, policy enforcement, durable economic memory, auditability, and dry-run payment planning. Live settlement is disabled by default.

## Security invariants

- Flow Memory does not accept private keys or seed phrases.
- Flow Memory does not move funds by default.
- Flow Memory does not broadcast transactions by default.
- Policy enforcement fails closed.
- Durable audit logging is required in production-planning mode.
- Provider failures, timeouts, stale quotes, and unknown prices are classified and auditable.
- Tenant/workspace fields are persisted on compute records when provided.

## Threat register

| Threat | Risk | Mitigation | Test coverage | Residual risk |
|---|---|---|---|---|
| Malicious task payloads | Payload attempts to inject unsafe payment or provider behavior. | Recursive unsafe field rejection for private keys, mnemonic, broadcast, transfer, withdraw, deposit; max body limits in HTTP gateway. | `test_unsafe_payloads_fail_closed_before_planning`, API unsafe-payload tests. | Semantic abuse can still require downstream review. |
| Quote manipulation | Provider reports distorted cost/latency. | Raw quote preservation, normalized quote output, provider reliability tracking, signed quote policy hooks. | Adapter validation tests; signed quote required policy path. | Real signature verification depends on future provider trust roots. |
| Stale quote exploitation | Route selected using stale prices. | Stale/expired status rejected unless policy explicitly allows. | Core stale quote tests. | Clock skew for external providers needs deployment-level monitoring. |
| Provider spoofing | Fake provider registered or selected. | Provider registry, provider-admin scope, verified-provider policy flag, audit event on mutations. | Admin scope and verified-provider policy tests. | Off-platform provider identity proof requires external PKI or DID review. |
| Provider outage | Planning crashes or blocks. | Bounded adapter timeout, retry policy, provider health status, Redis-backed distributed circuit breaker, and local circuit breaker fallback that can skip open-circuit providers. | Provider adapter, rate-limit, and circuit-breaker tests. | Redis or gateway control plane must be included in multi-node deployment. |
| Route poisoning | Malicious route inserted with unsafe settlement mode. | Provider-admin scope, dry-run required, settlement mode allowlist, unsafe payload rejection. | Policy fail-closed tests, admin scope tests. | Admin compromise remains high impact. |
| Policy bypass attempts | Payload weakens dry-run or marketplace policy. | `dry_run_required=false` rejected, no silent fallback, policy trace emitted. | Core unsafe dry-run and marketplace-only tests. | Policy object review is still needed for custom deployments. |
| Fallback abuse | Expensive fallback silently selected. | Fallback route flagged and rejected when fallback is disallowed; no silent fallback. | Fallback denied tests. | Operators must configure fallback budgets. |
| Budget exhaustion | Agent repeatedly requests expensive quotes/plans. | Budget limits, per-agent/per-goal/per-workspace fields, Redis-backed distributed rate limiter, local limiter for dev/test, and audit trail. | Budget exceeded tests; rate-limit tests. | API-gateway limits are still recommended at the edge. |
| Replay attacks | Duplicate writes or stale decision reuse. | Request IDs, idempotency keys, decision replay compares drift without mutating original. | Decision persistence/replay/idempotency tests. | Cross-service idempotency requires shared durable store. |
| Idempotency abuse | Reused key masks changed request. | Existing decision returned as idempotent replay and auditable; clients must scope keys per actor/request. | Service idempotency test. | Server-side idempotency payload equivalence enforcement is basic. |
| Audit log tampering | Decisions cannot be reconstructed. | Durable audit events include a deterministic hash chain with chain ID, sequence number, previous hash, canonical payload hash, and event hash; verification reports first broken sequence; local export/checkpoint verification detects tampered exports. | `tests/test_compute_market_audit.py` covers modified, missing, wrong previous-hash events, API/CLI verification, export verification, and tampered export failures. | Hash chaining and local exports are tamper-evident, not WORM; production must export checkpoints to immutable storage. |
| Cross-tenant data leakage | Tenant reads another tenant's records. | Tenant/workspace fields persisted and query filters supported. | Storage filter tests; scope tests. | The local router does not implement full tenant auth mapping. |
| Prompt injection in provider responses | Provider response attempts to alter policy. | Provider responses are parsed as data only; policy is local and immutable during quote normalization; provider contract validation rejects policy override attempts. | Invalid response, provider adapter, and provider contract tests. | Natural-language provider metadata must not be trusted by operators. |
| Unsafe payment payloads | User tries to create withdrawal, deposit, transfer, signing, or broadcast payload. | Recursive unsafe field rejection; dry-run payment plans only. | Unsafe private-key/mnemonic/broadcast/transfer tests. | Future live settlement must re-review all payload schemas. |
| Private-key exfiltration attempts | System asks for or stores secrets. | No CLI flags or API fields for private keys; config rejects `private_key_inputs_allowed=true`. | CLI/no private-key tests; config gate tests. | External provider credentials must be managed outside logs. |
| Accidental transaction broadcast | Dry-run payload sent to chain. | `broadcast_enabled=false`, `live_settlement_enabled=false`, `broadcast_allowed=false` in intents. | Payment and settlement tests. | External tools invoked by operators remain outside this boundary. |
| Settlement replay | Same settlement executed multiple times in future mode. | Live settlement gate requires idempotency, preflight simulation, limits, audit, and rollback. | Gate config tests. | Actual live settlement not implemented. |
| Quote cache poisoning | Bad cached quote selected. | Cache keyed by provider, route, task hash, policy hash; source/status stored; config-change invalidation field; external HTTP quotes are schema-filtered and raw-hashed; provider contract validation fails closed before onboarding. | Quote cache write/read tests, HTTP provider validation tests, provider contract tests. | Distributed cache invalidation policy must be operated with provider config rollout. |
| Denial of service | Huge payloads or unbounded queries. | HTTP max body bytes, pagination limit, rate-limit hook, bounded candidate routes. | HTTP and economic-memory pagination tests. | Local router is not a hardened internet edge. |
| Admin privilege abuse | Admin disables providers/routes or weakens policy. | Specific provider-admin/policy-admin/audit scopes, audit events for mutations. | Admin scope tests. | Admin identity lifecycle is deployment responsibility. |

## Required review before live settlement

Live settlement is outside production-planning mode. Before any live funds flow, complete the gates in `COMPUTE_MARKET_LIVE_SETTLEMENT_GATES.md`, add testnet-only integration tests, document the signing model, and obtain security/legal/compliance approval.
