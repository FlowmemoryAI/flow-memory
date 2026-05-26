# Flow Memory Compute Market Deployment

## Production safety defaults

Set or verify:

```text
FLOW_MEMORY_COMPUTE_MARKET_ENABLED=true
FLOW_MEMORY_COMPUTE_MARKET_MODE=production_planning
FLOW_MEMORY_COMPUTE_DATABASE_URL=sqlite:///.flow_memory/compute_market.sqlite3
FLOW_MEMORY_COMPUTE_STORAGE_BACKEND=sqlite
FLOW_MEMORY_COMPUTE_STORAGE_POOL_SIZE=4
FLOW_MEMORY_COMPUTE_STORAGE_TIMEOUT_MS=5000
FLOW_MEMORY_COMPUTE_MIGRATIONS_ENABLED=true
FLOW_MEMORY_COMPUTE_MIGRATIONS_AUTO_RUN=true
FLOW_MEMORY_COMPUTE_POSTGRES_SSL_MODE=require
FLOW_MEMORY_COMPUTE_STORAGE_MAX_OVERFLOW=4
FLOW_MEMORY_COMPUTE_STORAGE_STATEMENT_TIMEOUT_MS=5000
FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION=false
FLOW_MEMORY_COMPUTE_PROVIDER_REGISTRY_MODE=database
FLOW_MEMORY_COMPUTE_QUOTE_CACHE_TTL=300
FLOW_MEMORY_COMPUTE_PROVIDER_TIMEOUT_MS=2000
FLOW_MEMORY_COMPUTE_GLOBAL_PLANNING_TIMEOUT_MS=10000
FLOW_MEMORY_COMPUTE_MAX_CANDIDATE_ROUTES=64
FLOW_MEMORY_COMPUTE_MAX_QUOTE_CACHE_ENTRIES=10000
FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED=true
FLOW_MEMORY_COMPUTE_LIVE_SETTLEMENT_ENABLED=false
FLOW_MEMORY_COMPUTE_BROADCAST_ENABLED=false
FLOW_MEMORY_COMPUTE_PRIVATE_KEY_INPUTS_ALLOWED=false
FLOW_MEMORY_COMPUTE_AUDIT_REQUIRED=true
FLOW_MEMORY_COMPUTE_METRICS_ENABLED=true
FLOW_MEMORY_COMPUTE_TRACING_ENABLED=true
FLOW_MEMORY_COMPUTE_RATE_LIMITS_ENABLED=true
FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND=in_memory
FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND=in_memory
FLOW_MEMORY_COMPUTE_REDIS_URL=
FLOW_MEMORY_COMPUTE_REDIS_PREFIX=flow-memory:compute-market
FLOW_MEMORY_COMPUTE_RATE_LIMIT_ENABLED=true
FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_ENABLED=true
FLOW_MEMORY_COMPUTE_RATE_LIMIT_FAIL_CLOSED=true
FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_FAIL_CLOSED=true
FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_REQUIRED=false
FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI=
FLOW_MEMORY_COMPUTE_PROVIDER_CONTRACTS_REQUIRED=false
FLOW_MEMORY_COMPUTE_PROVIDER_CONTRACTS_VERIFIED=false
FLOW_MEMORY_COMPUTE_EXTERNAL_PROVIDER_ALLOWLIST=
FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED=false
FLOW_MEMORY_COMPUTE_ECONOMIC_MEMORY_WRITES_ENABLED=true
FLOW_MEMORY_COMPUTE_ADMIN_MUTATIONS_ENABLED=true
```

Do not commit real secrets. Provider credentials must be supplied through the deployment secret manager or environment variables and must never be logged.
SQLite is acceptable for local development and single-node deployments only. Multi-node production deployments should use the PostgreSQL-compatible adapter with `flow-memory[postgres]`, managed backups, restore drills, and migration promotion gates. The default local dependency set uses raw `sqlite3`; PostgreSQL is an optional production extra.

For the fastest safe container launch path, use `docker-compose.compute-market.yml` with `deployments/compute-market/live.env.example` as the environment template, then follow `docs/ops/COMPUTE_MARKET_LIVE_LAUNCH.md`.

## Multi-node production deployment

For horizontally scaled production planning, use:

- `FLOW_MEMORY_COMPUTE_STORAGE_BACKEND=postgres`
- `FLOW_MEMORY_COMPUTE_DATABASE_URL=postgresql://...`
- `FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION=true`
- `FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND=redis`
- `FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND=redis`
- `FLOW_MEMORY_COMPUTE_REDIS_URL=rediss://...`
- immutable audit export storage with object lock or equivalent WORM controls
- Render API deployment requires `RENDER_KEYVALUE_IP_ALLOWLIST=<public-egress-cidr>[,<public-egress-cidr>]` so the external TLS Key Value endpoint can be used safely.

SQLite remains appropriate for local development and single-node deployments only. Multi-node production requires managed PostgreSQL, automated backups, restore drills, migration promotion gates, advisory-lock-protected migrations, Redis-backed distributed abuse controls, and immutable audit export/checkpoint retention.

Blue/green and rolling deployments must run backward-compatible migrations before traffic shifts. Do not deploy code that requires a schema version newer than readiness reports. Rollback requires stopping writers, restoring the last known-good managed SQL snapshot, restoring or revalidating Redis state if required, and verifying audit checkpoints.

Disaster recovery requirements:

- database PITR or snapshots covering the compute-market RPO/RTO
- Redis persistence or accepted loss model for rate/circuit state
- immutable audit export checkpoints outside the primary database
- provider credential rotation procedure
- kill switches for compute market, external quotes, providers, routes, dry-run mode, and admin mutations



## Database migration

Fresh install:

```bash
python -m pytest tests/test_compute_market_production.py -q
flow-memory compute readiness --json
```

Application startup constructs `ComputeMarketStore`, creates `compute_market_records` and `compute_market_migrations`, and seeds default providers/routes/policy.
Production database requirements:

- Run migrations before serving compute traffic.
- Verify `flow-memory compute readiness --json` reports `migration_status.current=true`.
- Keep database snapshots before every deployment.
- Use `FLOW_MEMORY_COMPUTE_DATABASE_URL` for the storage binding. `FLOW_MEMORY_COMPUTE_MARKET_DATABASE_URL` remains backward-compatible, but new deployments should use `FLOW_MEMORY_COMPUTE_DATABASE_URL`.
- Set `FLOW_MEMORY_COMPUTE_STORAGE_BACKEND=sqlite` for local/single-node SQLite. Managed SQL deployments should use the schema notes in `docs/ops/COMPUTE_MARKET_PRODUCTION_CHECKLIST.md` and must not rely on process-local SQLite files.


Upgrade from alpha:

- Alpha economic memory was in-memory unless callers supplied records explicitly.
- If alpha records were exported, import them through `migrate_alpha_memory(store, records)`.
- No automatic alpha data migration is required when no durable alpha records exist.

Rollback:

- Stop API/CLI workers.
- Disable compute market or force dry-run-only mode while rolling back.
- Restore the last known-good managed SQL snapshot or SQLite database file.
- Revert code.
- Re-run migrations only after confirming the target schema version.
- Re-run `flow-memory compute readiness --json`.

## Provider configuration

1. Create provider with `compute:provider-admin` scope.
2. Configure supported unit types, networks, assets, settlement modes, quote TTL, reliability metadata, and health method/URL.
3. Create routes for the provider.
4. Run `flow-memory compute provider-health --provider <provider_id> --json`.
5. Run dry-run quote and plan smoke tests.

## Policy configuration

1. Start with default dry-run policy.
2. Set budget limits, allowed assets/networks/providers, denied providers, quote freshness, marketplace-only behavior, fallback behavior, and human-approval thresholds.
3. Keep `dry_run_required=true` unless live settlement gates are completed.
4. Validate policy through `POST /compute/policies/{policy_id}/validate`.

## Audit logs

Audit logs are durable `audit_event` records. Production planning mode requires audit logging. If audit write fails and policy requires audit logs, requests must fail closed.

Audit events are tamper-evident through a per-tenant/workspace hash chain. Use `GET /compute/audit/verify` or `flow-memory compute audit verify --json` during deployment and incident response. This detects modification, deletion, and broken previous-hash links; it is not WORM storage. Production deployments should export audit events to immutable storage.

Use `flow-memory compute audit export --chain-id all --out <path> --json` and `flow-memory compute audit verify-export --path <path> --json` to create and verify local checkpoint exports. Local files are not WORM. Production should write exports to immutable object storage with object-lock retention, legal hold where required, and lifecycle policies matching retention requirements.


## Metrics and tracing

Enable metrics and tracing in production planning mode. See `docs/COMPUTE_MARKET.md` for metric and span names.

Rate limiting and circuit breakers are local by default. Multi-node deployments should use the Redis-backed `RateLimiter` and `CircuitBreaker` implementations or enforce equivalent limits at the API gateway.
Redis-backed implementations are available through `RedisRateLimiter` and `RedisCircuitBreaker`. They are optional-dependency paths and fail closed by default when Redis is required but unavailable. Set fail-open only for explicitly accepted degraded-mode operations.


## Health and readiness

Runtime checks:

- `GET /compute/health`
- `GET /compute/readiness`
- `flow-memory compute health --json`
- `flow-memory compute readiness --json`

Readiness verifies compute market enabled, database reachable, migrations current, provider registry reachable, audit log writable, audit chain verifiable, quote cache reachable, rate limiter active, circuit breaker active, provider summary, migration plan, external quote configuration, and safety defaults.
Readiness fails or warns on migrations pending, invalid audit chains, unavailable Redis controls when configured, unsafe live-settlement/broadcast/private-key settings, and SQLite when managed SQL is required.

## Smoke tests

```bash
python -m pytest tests/test_compute_market_core.py tests/test_api_compute_endpoints.py tests/test_compute_market_production.py
flow-memory compute plan --task "run agent batch inference" --marketplace-only --asset USDC --network solana --dry-run --json
flow-memory compute quote --task "run agent batch inference" --json
flow-memory compute providers --json
flow-memory compute routes --json
flow-memory compute policies --json
flow-memory compute economic-memory --json
flow-memory compute readiness --json
flow-memory compute audit verify --json
flow-memory compute audit export --chain-id all --out release_evidence/audit_export.ndjson --json
flow-memory compute audit verify-export --path release_evidence/audit_export.ndjson --json
flow-memory compute provider-contract validate tests/fixtures/compute_market/valid_quote.json --json
```

## Kill switches

- Disable compute market: `FLOW_MEMORY_COMPUTE_MARKET_ENABLED=false`.
- Disable provider: `POST /compute/providers/{provider_id}/disable`.
- Disable route: `POST /compute/routes/{route_id}/disable`.
- Force dry-run-only mode: `FLOW_MEMORY_COMPUTE_DRY_RUN_REQUIRED=true`.
- Disable external provider quotes: `FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED=false`.
- Disable economic memory writes: `FLOW_MEMORY_COMPUTE_ECONOMIC_MEMORY_WRITES_ENABLED=false`.
- Disable admin mutations: `FLOW_MEMORY_COMPUTE_ADMIN_MUTATIONS_ENABLED=false`.

## Incident response

1. Force dry-run-only mode.
2. Disable suspicious providers/routes.
3. Export audit events for affected request IDs.
4. Re-run decision replay for affected decisions.
5. Preserve quote snapshots and economic memory.
6. Rotate provider credentials if external quote APIs are involved.
7. Document residual risk and release patch.
