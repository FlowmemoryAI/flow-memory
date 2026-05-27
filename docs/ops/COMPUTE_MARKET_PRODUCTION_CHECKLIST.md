# Flow Memory Compute Market Production Checklist

## Release status

Recommended release label: Flow Memory Compute Market Multi-Node Production Planning Release.

## Required gates

- [ ] `python -m pytest`
- [ ] `python -m ruff check .`
- [ ] `python -m mypy src tests` or documented production target
- [ ] `git diff --check`
- [ ] OpenAPI snapshot validation
- [ ] Naming audit
- [ ] Safety audit
- [ ] Migration test
- [ ] CLI smoke tests
- [ ] API smoke tests
- [ ] Audit chain verification
- [ ] Rate-limit/circuit-breaker hardening tests
- [ ] HTTP provider SSRF/validation tests
- [ ] Intelligence utility API, CLI, and usage-ledger tests
- [ ] Price history, anomaly, and forecast tests

- [ ] PostgreSQL storage adapter tests
- [ ] Redis rate limiter/circuit breaker tests
- [ ] Audit export/checkpoint verification
- [ ] Provider contract validation tests
## Production target typecheck

If full-repo mypy is blocked by unrelated legacy typing debt, the minimum production target is:

```bash
python -m mypy src/flow_memory/compute_market src/flow_memory/api/compute_endpoints.py
```

Expanded multi-node production target:

```bash
python -m mypy src/flow_memory/compute_market src/flow_memory/api/compute_endpoints.py src/flow_memory/cli.py scripts/export_release_evidence.py tests/test_compute_market_storage.py tests/test_compute_market_rate_limits.py tests/test_compute_market_audit.py tests/test_compute_market_provider_adapters.py tests/test_compute_market_provider_contracts.py tests/test_compute_market_production.py tests/test_api_compute_endpoints.py
```

Do not claim full-repo mypy passes unless it does.

## Ruff policy

Production code must pass `python -m ruff check .`. Benchmark files may be exempted only for documented non-production reasons. Current rationale: RL benchmark scripts are non-production measurement harnesses with historical path-bootstrap and compact script formatting; production compute-market code is not excluded.

## Safety checks

- [ ] `live_settlement_enabled=false`
- [ ] `broadcast_enabled=false`
- [ ] `private_key_inputs_allowed=false`
- [ ] unsafe payload tests pass
- [ ] dry-run payment/settlement tests pass
- [ ] audit persistence tests pass
- [ ] provider-admin and policy-admin scope tests pass
- [ ] decision replay does not mutate original decisions

- [ ] audit hash-chain verification passes
- [ ] rate-limited requests create audit events
- [ ] open provider circuits are skipped in planning
- [ ] intelligence-plan dry-run safety tests confirm no funds, private keys, or broadcast
- [ ] intelligence usage ledger records estimated/actual economics without debiting real credits
- [ ] price history/anomaly APIs work from persisted quote snapshots
## Deployment checks

- [ ] Database migration creates compute market records and indexes.
- [ ] Provider registry is seeded and durable.
- [ ] Route registry is seeded and durable.
- [ ] Default policy is seeded and durable.
- [ ] Economic memory records are durable.
- [ ] Audit events are durable.
- [ ] Health/readiness endpoints return OK.
- [ ] Rollback plan is documented in `COMPUTE_MARKET_DEPLOYMENT.md`.

- [ ] Audit events are tamper-evident and verifiable.
- [ ] Rate limiter and circuit breaker status are visible in readiness.
- [ ] HTTP quote providers are disabled unless explicitly configured.
- [ ] Managed SQL backup/restore plan is documented for production.
- [ ] `FLOW_MEMORY_COMPUTE_REQUIRE_MANAGED_SQL_IN_PRODUCTION=true` is set for multi-node production.
- [ ] Redis URL is configured when `FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND=redis` or `FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND=redis`.
- [ ] Audit export/checkpoint files verify before deployment and are shipped to immutable object storage.
- [ ] Provider quote contract validation passes for every external provider sample.
- [ ] `/compute/intelligence-plan` returns a tier, reasoning budget, run decision, and safe next actions.
- [ ] `/compute/prices`, `/compute/prices/history`, `/compute/prices/anomalies`, and `/compute/prices/forecast` return persisted price memory.
- [ ] `/compute/usage`, `/compute/usage/by-agent/{agent_id}`, `/compute/usage/by-goal/{goal_id}`, and `/compute/usage/statement` return usage ledger accounting records.
- [ ] Provider applications include `provider_class`, and intelligence plans expose `recommended_provider_classes`.
## OpenAPI/API snapshot

Regenerate after API changes:

```bash
python scripts/export_api_snapshot.py --write docs/API_SNAPSHOT.json
python -c "import json; from pathlib import Path; from flow_memory.api.openapi import openapi_schema; Path('docs/openapi/flow-memory.openapi.json').write_text(json.dumps(openapi_schema(), indent=2, sort_keys=True)+'\\n', encoding='utf-8')"
```

Intelligence utility snapshot changes must include the endpoints above plus CLI smoke coverage for:

```bash
flow-memory compute intelligence-plan --task "research competitor repo" --estimated-value 50 --budget 5 --allow-background --json
flow-memory compute prices --json
flow-memory compute usage --agent-id research-agent --json
flow-memory compute statement --json
```
## Hardening test slice

```bash
python -m pytest tests/test_compute_market_storage.py tests/test_compute_market_audit.py tests/test_compute_market_rate_limits.py tests/test_compute_market_provider_adapters.py tests/test_compute_market_provider_contracts.py

```
Managed SQL deployment notes:

- SQLite is local/single-node only.
- PostgreSQL storage is available through `FLOW_MEMORY_COMPUTE_STORAGE_BACKEND=postgres` and `flow-memory[postgres]`.
- The PostgreSQL adapter uses parameterized queries, JSONB payloads, timestamptz timestamps, advisory-lock migrations, and per-table indexes for provider, route, policy, decision, audit, economic memory, quote cache, and idempotency lookups.
- Rollback requires a database snapshot restore; do not downgrade schema in place under traffic.
- Redis-backed controls should use `FLOW_MEMORY_COMPUTE_RATE_LIMIT_BACKEND=redis`, `FLOW_MEMORY_COMPUTE_CIRCUIT_BREAKER_BACKEND=redis`, and fail-closed defaults unless a documented degraded mode is approved.
## Naming audit

Run:

```bash
rg -n "squire|Squire|SQUIRE|square|Square|correlation|Correlation"
```

Acceptable hits are limited to historical notes, tests proving legacy naming is absent, repository paths, or ordinary unrelated usage.

## Safety audit

Run:

```bash
rg -n "private_key|seed phrase|mnemonic|broadcast|sendTransaction|signTransaction|mainnet|custody|transfer|withdraw|deposit|settle|settlement"
```

Classify every hit. Production-acceptable hits must document rejection, dry-run behavior, disabled broadcast, tests, or security gates.
