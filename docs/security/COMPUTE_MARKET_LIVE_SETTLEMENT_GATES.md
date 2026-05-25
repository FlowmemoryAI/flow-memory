# Flow Memory Compute Market Live Settlement Gates

Live settlement is disabled by default.

Current code defaults:

- `live_settlement_enabled = false`
- `broadcast_enabled = false`
- `private_key_inputs_allowed = false`
- `dry_run_required = true`

Flow Memory Compute Market is production-ready for planning, quote normalization, route selection, budget policy enforcement, economic memory, dry-run payment planning, provider integrations, observability, admin operations, and auditability. It is not live-settlement production-ready.

## Required gates

Live settlement must remain unreachable unless all gates pass:

1. Explicit config flag: `live_settlement_enabled=true`.
2. Explicit production settlement environment configured.
3. Explicit admin approval with `compute:settlement-admin`.
4. Explicit policy: `dry_run_required=false` and `settlement_modes_allowed` includes the requested mode.
5. Explicit provider support: provider is verified and supports live settlement.
6. Explicit audit: `audit_required=true`, durable audit write succeeds, and `flow-memory compute audit verify --json` reports a valid hash chain before and after settlement simulation.
7. Explicit idempotency: idempotency key required and persisted.
8. Explicit signing model: non-custodial or approved custody model documented.
9. Explicit transaction simulation: preflight simulation required.
10. Explicit limits: max transaction amount, daily limit, per-agent limit, and per-workspace limit.
11. Explicit network allowlist: no accidental mainnet/testnet confusion.
12. Explicit security review: reviewed and approved.
13. Explicit test coverage: live settlement tests use mocks or testnet only.
14. Explicit rollback: kill switch documented and rehearsed.

## Kill switches

- Disable compute market: `FLOW_MEMORY_COMPUTE_MARKET_ENABLED=false`.
- Force dry-run-only mode: `FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED=true`.
- Disable live settlement: `FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED=false`.
- Disable broadcast: `FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED=false`.
- Disable external quotes: `FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED=false`.
- Disable economic memory writes: `FLOW_MEMORY_COMPUTE_ECONOMIC_MEMORY_WRITES_ENABLED=false`.
- Disable admin mutations: `FLOW_MEMORY_COMPUTE_ADMIN_MUTATIONS_ENABLED=false`.
- Disable provider or route through provider-admin endpoints/CLI.

## Required implementation before enabling

- Dedicated settlement service separated from planning.
- Transaction preflight simulator with deterministic evidence.
- Non-custodial signing integration or approved custody model.
- Testnet-only integration tests.
- Per-provider settlement allowlist.
- Per-network allowlist.
- Idempotent settlement-intent store.
- Tamper-evident audit chain for settlement actions.
- Immutable export of audit-chain checkpoints to WORM or equivalent object-lock storage.
- Incident runbook.
- Compliance approval.

## Prohibited until gates pass

- Private-key or seed phrase inputs.
- Mainnet broadcast.
- Automatic fund movement.
- Silent fallback to live payment mode.
- Provider response controlled policy changes.
- Auto-approval above human threshold.
