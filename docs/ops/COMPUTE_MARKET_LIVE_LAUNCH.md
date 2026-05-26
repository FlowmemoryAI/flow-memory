# Flow Memory Compute Market live launch runbook

This runbook is for the fastest safe **Level 1 — Production Planning Live** launch. It deliberately keeps payment and settlement dry-run only.

## What this launches

- Hosted HTTP API boundary for `/compute/*` planning endpoints.
- Managed PostgreSQL storage when `FLOW_MEMORY_COMPUTE_DATABASE_URL` points at your provider; the bundled Compose PostgreSQL service is only a private smoke fallback.
- Redis-backed distributed rate limiting and provider circuit breaking when `FLOW_MEMORY_COMPUTE_REDIS_URL` points at managed TLS Redis (`rediss://...`); the bundled Compose Redis service is only a private smoke fallback.
- Local audit export/checkpoint file suitable for handoff to immutable object storage.
- API-key plus scope enforcement at the Flow Memory gateway.

It does **not** launch live settlement, signing, custody, private-key input, transaction broadcast, Stripe checkout, or funds movement.

## Fastest container path

1. Copy the environment template into your secret manager or an untracked local file:

```bash
cp deployments/compute-market/live.env.example .env.compute-market.live
```

2. Fill every `CHANGEME` value. Do not commit the filled file.
   For Render API provisioning, export `RENDER_API_KEY`, `RENDER_OWNER_ID`, `RENDER_KEYVALUE_IP_ALLOWLIST`, and `FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI` in the shell before running `scripts/deploy_compute_market_render_level1.py`. `RENDER_KEYVALUE_IP_ALLOWLIST` must contain the public egress CIDR ranges allowed to reach the external `rediss://` Key Value endpoint. Set `RENDER_POSTGRES_PLAN`, `RENDER_KEYVALUE_PLAN`, and `RENDER_SERVICE_PLAN` to production-grade paid plans; `RENDER_ALLOW_FREE_PLANS=true` is reserved for non-production smoke deployments only.
   Keep `FLOW_MEMORY_BILLING_STRIPE_CHECKOUT_ENABLED=false` for Level 1. If paid credits are enabled in a later gate, put Stripe API and webhook secrets only in the deployment secret manager and keep `FLOW_MEMORY_BILLING_STRIPE_WEBHOOK_TOLERANCE_SECONDS` set to a bounded replay window.

3. Start the planning stack:

```bash
docker compose --env-file .env.compute-market.live -f docker-compose.compute-market.yml up --build
```

For a private smoke run without managed PostgreSQL/Redis, set the template URLs to `postgres`/`redis` service hosts and add `--profile local-infra`. Do not use that bundled profile as the public production database/Redis plan.

4. Verify health and readiness through the gateway:

```bash
curl -fsS \
  -H "x-flow-memory-api-key: $FLOW_MEMORY_API_KEY" \
  -H "x-flow-memory-scopes: compute:read" \
  http://127.0.0.1:8765/compute/health

curl -fsS \
  -H "x-flow-memory-api-key: $FLOW_MEMORY_API_KEY" \
  -H "x-flow-memory-scopes: compute:read" \
  http://127.0.0.1:8765/compute/readiness
```

5. Verify dry-run planning:

```bash
curl -fsS \
  -H "content-type: application/json" \
  -H "x-flow-memory-api-key: $FLOW_MEMORY_API_KEY" \
  -H "x-flow-memory-scopes: compute:plan" \
  --data '{"task":"actual live readiness verification","dry_run":true}' \
  http://127.0.0.1:8765/compute/plan
```

6. Verify audit integrity:

```bash
curl -fsS \
  -H "x-flow-memory-api-key: $FLOW_MEMORY_API_KEY" \
  -H "x-flow-memory-scopes: compute:audit" \
  http://127.0.0.1:8765/compute/audit/verify
```

## External ingress requirements

Place the API behind production TLS, network allowlists or WAF, request logging, and your real identity provider. The built-in API key and scope header are a minimal gateway guardrail, not a full customer authentication system.

## Required readiness posture

A public live deployment should not receive traffic unless `/compute/readiness` reports:

- `ready=true`
- PostgreSQL backend and current migrations
- Redis rate limiter and circuit breaker configured
- audit writable and audit chain valid
- dry-run required
- live settlement disabled
- broadcast disabled
- private-key inputs disabled

## Level 2 provider quote cutover

Before enabling real provider quotes:

1. Validate the provider's quote sample:

```bash
flow-memory compute provider-contract validate provider-quote.json --json
```

2. Configure an HTTPS endpoint on the allowlist only.
3. Store provider credentials in the deployment secret manager.
4. Run sandbox quote calls and verify stale, expired, unknown-price, timeout, retry, and circuit-breaker behavior.
5. Set `FLOW_MEMORY_COMPUTE_EXTERNAL_QUOTES_ENABLED=true`, `FLOW_MEMORY_COMPUTE_EXTERNAL_PROVIDER_ALLOWLIST=<host>`, and `FLOW_MEMORY_COMPUTE_PROVIDER_CONTRACTS_VERIFIED=true` only after the checks pass.

## Immutable audit handoff

The local export is tamper-evident but not WORM. Production must copy `FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI` outputs/checkpoints to object-lock storage and verify the object retention metadata out of band.
