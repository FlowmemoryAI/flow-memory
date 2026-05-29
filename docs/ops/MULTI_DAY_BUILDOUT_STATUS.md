# Multi-day buildout status

Date: 2026-05-26
Branch: `work/squire-v2`
Latest inspected commit: `8d9c685 Update full mypy evidence commit`

## Current architecture

```mermaid
flowchart TD
    Agent[Agent or operator] --> API[Flow Memory API router]
    API --> Compute[Compute Market service]
    API --> Inference[Inference Market service]
    API --> Capacity[Capacity Market service]
    API --> Futures[GPU Futures simulator]
    Compute --> Planner[Planner and policy engine]
    Compute --> Store[Compute market storage]
    Inference --> Store
    Capacity --> Store
    Futures --> Store
    Compute --> Audit[Tamper-evident audit chain]
    Compute --> Controls[Rate limits and circuit breakers]
    Store --> SQLite[Local SQLite]
    Store --> Postgres[Managed Postgres path]
    Controls --> Memory[In-memory local controls]
    Controls --> Redis[Managed Redis path]
    Compute --> Providers[Provider registry and quote adapters]
    Providers --> Sandbox[Provider sandbox conformance]
```

## What exists

- Compute Market planning, routing, dry-run payment planning, settlement simulation, audit, provider onboarding, quote validation, quote cache, quote drift, price history, price forecast, usage statements, jobs, billing ledger, capacity reservations, provider reputation, health/readiness, telemetry, alerts, Render deployment automation, Postgres path, and Redis path.
- Flow Memory Inference Market models, deterministic resale fixtures, run-vs-sell opportunity planner, OpenAI-compatible fake proxy path, demand snapshots, usage records, API endpoints, CLI commands, lazy API binding to the active compute-market store, and persistence-backed record families.
- Flow Memory Capacity Market and Forward Capacity simulators exist with dry-run inventory, quotes, holds, reservations, delivery schedules, settlement simulation records, CLI commands, APIs, lazy API binding to the active compute-market store, and persistence-backed record families.
- Flow Memory GPU Futures Simulator exists with simulated contracts, orders, positions, mark/index prices, risk checks, delivery/expiry/settlement simulations, CLI commands, APIs, lazy API binding to the active compute-market store, and persistence-backed record families.
- Safety defaults and live-settlement gates are implemented in Compute Market code, market simulators, docs, and deployment validation.

## Partial areas

- The new inference, capacity, forward-capacity, and futures services are simulator-grade; real provider credentials, real provider execution, and real billing providers are not bound.
- New market API services now attach lazily to the active compute-market store, so public API traffic uses the configured SQLite/Postgres storage path instead of a detached process-only singleton.
- Deployment automation exists, but no real public managed Postgres, managed Redis, domain, TLS URL, production API key, object-lock audit storage, or Render API credentials are present in the environment.

## Missing buildout blocks

- Real external inference credit seller onboarding and provider credential operations.
- Real provider quote ingestion with production credentials and allowlists.
- Real compute execution against external providers and artifact storage.
- External billing/prepaid credits with webhook credentials.
- Immutable object-lock audit storage binding.
- JWT/OIDC/API gateway production integration beyond API key and scope headers.
- Public Level 1 deployment and smoke tests against a managed Postgres and managed Redis URL.
- Legal/compliance/security review for any future live settlement, forward-capacity, or futures path.

## Active blockers

- `RENDER_API_KEY` is not available.
- `FLOW_MEMORY_PUBLIC_API_URL` is not available.
- `FLOW_MEMORY_COMPUTE_DATABASE_URL` for managed Postgres is not available.
- `FLOW_MEMORY_COMPUTE_REDIS_URL` for managed Redis is not available.
- `FLOW_MEMORY_COMPUTE_AUDIT_EXPORT_URI` for immutable object storage is not available.
- No external provider credentials or allowlist are available.
- No billing provider credentials are available.
- No legal/compliance/security approval exists for live settlement, live forward-capacity instruments, or live futures.

## Planned work order

```mermaid
flowchart TD
    A[Research notes] --> B[Inference Market core]
    B --> C[Agent run-vs-sell planner]
    C --> D[Inference API and CLI]
    D --> E[Base URL proxy]
    E --> F[Demand and usage ledger]
    F --> G[Capacity package]
    G --> H[Forward capacity simulator]
    H --> I[GPU futures simulator]
    I --> J[Docs and OpenAPI]
    J --> K[Verification and release evidence]
```

## Safety status

```mermaid
flowchart LR
    Request[Market request] --> Guard[Unsafe payload guard]
    Guard --> DryRun[Dry-run policy]
    DryRun --> Audit[Audit event]
    DryRun --> Sim[Simulation result]
    Guard -. rejects .-> Unsafe[Private keys, broadcast, live settlement, live futures, margin, leverage]
```

Current safe defaults remain required:

- `dry_run_only=true`
- `funds_moved=false`
- `broadcast_allowed=false`
- `private_key_required=false`
- `live_trading_enabled=false` for futures
- `legal_review_required=true` for forward capacity and futures
- `compliance_review_required=true` for forward capacity and futures

## Checkpoint 2026-05-26

Files added:

- `AGENTS.md`
- `docs/ops/MULTI_DAY_BUILDOUT_STATUS.md`

Tests run: pending for this checkpoint.
Commit: pending.
Next phase: research artifacts and inference market foundation.

## Checkpoint 2026-05-26 Inference, capacity, and futures alpha

Files changed:

- `src/flow_memory/inference_market/`
- `src/flow_memory/capacity_market/`
- `src/flow_memory/futures_market/`
- `src/flow_memory/api/router.py`
- `src/flow_memory/api/manifest.py`
- `src/flow_memory/api/scopes.py`
- `src/flow_memory/cli.py`
- `docs/API_SNAPSHOT.json`
- `docs/openapi/flow-memory.openapi.json`
- `tests/test_inference_capacity_futures_markets.py`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py -q`
- `python -m pytest tests/test_inference_capacity_futures_markets.py tests/test_api_openapi_snapshot.py tests/test_api_snapshot.py tests/test_compute_market_naming.py -q`
- `python -m pytest tests/test_api_auth.py tests/test_api_auth_scopes.py -q`
- `python -m ruff check src/flow_memory/inference_market src/flow_memory/capacity_market src/flow_memory/futures_market src/flow_memory/api/marketplace_endpoints.py tests/test_inference_capacity_futures_markets.py`
- `python scripts/check_compute_market_production.py`
- `python -m mypy src tests scripts --config-file pyproject.toml`

Commits:

- `2f88883 Add inference capacity futures simulators`

Safety status:

- Inference, capacity, forward-capacity, and futures behavior remains dry-run or simulation-only.
- External providers remain disabled by default.
- Futures remain non-live with legal and compliance review flags.

```mermaid
flowchart TD
    Inference[Inference Market Alpha] --> AgentEconomy[Run vs sell planner]
    Inference --> Proxy[OpenAI-compatible fake proxy]
    AgentEconomy --> Usage[Usage and ROI ledger]
    Capacity[Capacity Market Simulator] --> Holds[Holds and reservations]
    Capacity --> Forwards[Forward capacity simulation]
    Futures[GPU Futures Simulator] --> Orders[Simulated orders]
    Futures --> Risk[Simulation risk checks]
    Proxy --> Safety[Dry-run safety envelope]
    Holds --> Safety
    Forwards --> Safety
    Orders --> Safety
```

## Checkpoint 2026-05-26 Persistence follow-up

Files changed:

- `src/flow_memory/compute_market/storage.py`
- `src/flow_memory/compute_market/storage_backends.py`
- `src/flow_memory/inference_market/service.py`
- `src/flow_memory/capacity_market/service.py`
- `src/flow_memory/futures_market/service.py`
- `tests/test_inference_capacity_futures_markets.py`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py -q`
- `python -m ruff check src/flow_memory/inference_market/service.py src/flow_memory/capacity_market/service.py src/flow_memory/futures_market/service.py src/flow_memory/compute_market/storage.py src/flow_memory/compute_market/storage_backends.py tests/test_inference_capacity_futures_markets.py`
- `python -m mypy src/flow_memory/inference_market src/flow_memory/capacity_market src/flow_memory/futures_market src/flow_memory/compute_market src/flow_memory/api tests/test_inference_capacity_futures_markets.py --config-file pyproject.toml`
- `python scripts/check_compute_market_production.py`
- `git diff --check -- src/flow_memory/inference_market/service.py src/flow_memory/capacity_market/service.py src/flow_memory/futures_market/service.py src/flow_memory/compute_market/storage.py src/flow_memory/compute_market/storage_backends.py tests/test_inference_capacity_futures_markets.py`

Commits:

- `7819d2c Persist market simulator records`

Blockers:

- Public Level 1 deployment still requires external Render credentials, managed Postgres, managed Redis, public URL, API secret, object-lock audit URI, and production provider allowlist.
- Live provider quotes, live billing, live settlement, and live futures remain intentionally blocked.

```mermaid
flowchart TD
    MarketServices[Market simulator services] --> Store[ComputeMarketStore JSON records]
    Store --> SQLite[SQLite local store]
    Store --> Postgres[Postgres schema generator]
    InferenceRecords[Inference record families] --> Store
    CapacityRecords[Capacity and forward record families] --> Store
    FuturesRecords[Futures simulation record families] --> Store
    Postgres --> ManagedDB[Managed Postgres when credentials exist]
    SQLite --> LocalTests[Persistence tests]
```

## Checkpoint 2026-05-26 Inference admin hardening

Files changed:

- `src/flow_memory/inference_market/service.py`
- `src/flow_memory/api/marketplace_endpoints.py`
- `tests/test_inference_capacity_futures_markets.py`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py -q`
- `python -m ruff check src/flow_memory/inference_market/service.py src/flow_memory/api/marketplace_endpoints.py tests/test_inference_capacity_futures_markets.py`
- `python -m mypy src/flow_memory/inference_market src/flow_memory/api/marketplace_endpoints.py tests/test_inference_capacity_futures_markets.py --config-file pyproject.toml`
- `python scripts/check_compute_market_production.py`
- `python -m mypy src tests scripts --config-file pyproject.toml`
- `git diff --check -- src/flow_memory/inference_market/service.py src/flow_memory/api/marketplace_endpoints.py tests/test_inference_capacity_futures_markets.py`

Commits:

- `51fe87e Harden inference market admin endpoints`

Implementation:

- Inference credit account creation, source create/update/disable/health, cancel-listing, and demand snapshot endpoints now delegate to stateful service methods.
- These state changes persist through the same compute-market record store when a store is attached.
- Raw provider credentials are rejected; `credential_ref` remains the only accepted secret reference field.

```mermaid
flowchart TD
    Admin[Inference admin request] --> Guard[Unsafe payload and raw credential guard]
    Guard --> Source[Source account listing demand service]
    Source --> Memory[In-memory simulator state]
    Source --> Store[Optional ComputeMarketStore persistence]
    Store --> Records[Inference source account listing demand records]
    Guard -. rejects .-> Unsafe[Raw provider keys or private key payloads]
```

## Checkpoint 2026-05-26 CLI alias coverage

Files changed:

- `src/flow_memory/cli.py`
- `tests/test_inference_capacity_futures_markets.py`
- `docs/INFERENCE_MARKET.md`
- `docs/CAPACITY_MARKET.md`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py -q`
- `python -m ruff check src/flow_memory/cli.py tests/test_inference_capacity_futures_markets.py src/flow_memory/inference_market/service.py src/flow_memory/api/marketplace_endpoints.py`
- `python -m mypy src/flow_memory/cli.py src/flow_memory/inference_market src/flow_memory/api/marketplace_endpoints.py tests/test_inference_capacity_futures_markets.py --config-file pyproject.toml`
- `python scripts/check_compute_market_production.py`

Commits:

- `939ad0b Add nested market CLI aliases`

Implementation:

- `flow-memory inference credits list`
- `flow-memory inference credits buy`
- `flow-memory inference credits sell`
- `flow-memory capacity forward quote`
- `flow-memory capacity forward simulate`
- `flow-memory capacity forward simulate-delivery`
- `flow-memory capacity forward list`
- `flow-memory capacity index`
- `flow-memory capacity forward-curve`

```mermaid
flowchart TD
    CLI[Flow Memory CLI] --> InferenceCredits[inference credits nested aliases]
    CLI --> CapacityForward[capacity forward nested aliases]
    CLI --> CapacityIndexes[capacity index and forward curve]
    InferenceCredits --> InferenceService[Inference Market service]
    CapacityForward --> CapacityService[Capacity Market service]
    CapacityIndexes --> FuturesIndexes[Capacity index simulator]
```

## Checkpoint 2026-05-26 Marketplace API persistence binding

Files changed:

- `src/flow_memory/api/marketplace_endpoints.py`
- `tests/test_inference_capacity_futures_markets.py`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py -q`
- `python -m ruff check src/flow_memory/api/marketplace_endpoints.py tests/test_inference_capacity_futures_markets.py`
- `python -m mypy src/flow_memory/api/marketplace_endpoints.py src/flow_memory/inference_market src/flow_memory/capacity_market src/flow_memory/futures_market tests/test_inference_capacity_futures_markets.py --config-file pyproject.toml`
- `python -m pytest tests/test_api_auth.py tests/test_api_auth_scopes.py tests/test_api_openapi_snapshot.py tests/test_api_snapshot.py -q`
- `python scripts/check_compute_market_production.py`
- `git diff --check -- src/flow_memory/api/marketplace_endpoints.py tests/test_inference_capacity_futures_markets.py docs/ops/MULTI_DAY_BUILDOUT_STATUS.md`

Commit:

- `27e2baf Bind market APIs to compute store`

Implementation:

- `/inference/*`, `/capacity/*`, `/capacity/forwards/*`, and `/futures/*` endpoint adapters now lazily bind their simulator services to `default_service().store`.
- The endpoint adapters rebuild their service wrapper when the active compute-market service changes, which keeps tests and production configuration aligned.
- API regression coverage verifies inference admin source creation, capacity reservation, and futures simulated orders persist to the active compute-market store.

```mermaid
flowchart TD
    Request[Market API request] --> Router[API router]
    Router --> Adapter[Marketplace endpoint adapter]
    Adapter --> DefaultCompute[Active Compute Market service]
    DefaultCompute --> Store[Configured ComputeMarketStore]
    Adapter --> Inference[Inference Market wrapper]
    Adapter --> Capacity[Capacity Market wrapper]
    Adapter --> Futures[Futures simulator wrapper]
    Inference --> Store
    Capacity --> Store
    Futures --> Store
    Store --> SQLite[SQLite local]
    Store --> Postgres[Managed Postgres path]
```

## Checkpoint 2026-05-26 Anthropic-compatible proxy

Files changed:

- `src/flow_memory/inference_market/service.py`
- `src/flow_memory/api/marketplace_endpoints.py`
- `src/flow_memory/api/router.py`
- `src/flow_memory/api/manifest.py`
- `docs/API_SNAPSHOT.json`
- `docs/openapi/flow-memory.openapi.json`
- `docs/INFERENCE_PROXY.md`
- `tests/test_inference_capacity_futures_markets.py`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py tests/test_api_openapi_snapshot.py tests/test_api_snapshot.py tests/test_compute_market_naming.py -q`
- `python -m ruff check src/flow_memory/inference_market/service.py src/flow_memory/api/marketplace_endpoints.py src/flow_memory/api/router.py src/flow_memory/api/manifest.py tests/test_inference_capacity_futures_markets.py`
- `python -m mypy src/flow_memory/inference_market src/flow_memory/api/marketplace_endpoints.py src/flow_memory/api/manifest.py tests/test_inference_capacity_futures_markets.py --config-file pyproject.toml`
- `python scripts/check_compute_market_production.py`

Commit:

- `5cd3f98 Add Anthropic-compatible inference proxy`

Implementation:

- Added a seeded Anthropic-compatible credit source, balance, and listing for the local dry-run marketplace.
- Added `GET /anthropic/v1/models` and `POST /anthropic/v1/messages`.
- OpenAI and Anthropic proxy responses now attach an inference usage record and persist it through the active compute-market store.
- External provider credentials remain disabled by default; the proxy still uses deterministic fake provider output.

```mermaid
sequenceDiagram
    participant SDK as Anthropic SDK
    participant API as Flow Memory API
    participant Market as Inference Market
    participant Store as ComputeMarketStore
    SDK->>API: POST /anthropic/v1/messages
    API->>Market: Route under inference proxy policy
    Market->>Market: Select dry-run compatible listing
    Market->>Store: Persist route quote and usage
    Market-->>API: Anthropic-compatible fake message
    API-->>SDK: dry_run_only response
```

## Checkpoint 2026-05-26 Marketplace audit-chain binding

Files changed:

- `src/flow_memory/inference_market/service.py`
- `src/flow_memory/capacity_market/service.py`
- `src/flow_memory/futures_market/service.py`
- `tests/test_inference_capacity_futures_markets.py`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py -q`
- `python -m ruff check src/flow_memory/inference_market/service.py src/flow_memory/capacity_market/service.py src/flow_memory/futures_market/service.py tests/test_inference_capacity_futures_markets.py`
- `python -m mypy src/flow_memory/inference_market src/flow_memory/capacity_market src/flow_memory/futures_market tests/test_inference_capacity_futures_markets.py --config-file pyproject.toml`
- `python scripts/check_compute_market_production.py`

Commit:

- `c89b318 Bind market actions to audit chains`

Implementation:

- Inference market buy, sell, opportunity-cost, OpenAI proxy, and Anthropic proxy operations now append tamper-evident audit events when a compute-market store is attached.
- Capacity hold, reserve, release, forward draft, forward simulation, and delivery simulation now append tamper-evident audit events when a compute-market store is attached.
- Futures simulated orders, cancellations, risk checks, expiry, delivery, and settlement simulations now append tamper-evident audit events when a compute-market store is attached.
- Regression tests verify `inference-market`, `capacity-market`, and `futures-simulator` audit chains survive store reopen and pass hash-chain verification.

```mermaid
flowchart TD
    InferenceAction[Inference market action] --> AuditWriter[Store audit append]
    CapacityAction[Capacity market action] --> AuditWriter
    FuturesAction[Futures simulator action] --> AuditWriter
    AuditWriter --> Chain[Chain-specific audit hash chain]
    Chain --> Verify[verify_audit_chain]
    Verify --> Evidence[Regression evidence]
```

## Checkpoint 2026-05-26 Proxy scope and streaming hardening

Files changed:

- `src/flow_memory/inference_market/service.py`
- `tests/test_inference_capacity_futures_markets.py`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py -q`
- `python -m ruff check src/flow_memory/inference_market/service.py tests/test_inference_capacity_futures_markets.py`
- `python -m mypy src/flow_memory/inference_market tests/test_inference_capacity_futures_markets.py --config-file pyproject.toml`
- `python scripts/check_compute_market_production.py`

Commit:

- `dabba23 Harden inference proxy scope behavior`

Implementation:

- OpenAI-compatible and Anthropic-compatible proxy responses now include a deterministic `request_id`.
- If a caller asks for streaming while the local fake provider path is active, the response explicitly returns `streaming_not_implemented` inside `flow_memory.warnings` instead of silently pretending to stream.
- HTTP gateway coverage now verifies the Anthropic-compatible proxy requires `inference:proxy`, denies `inference:read`, records usage, and leaves the inference audit chain valid.

```mermaid
flowchart TD
    SDK[Compatible SDK] --> Gateway[HTTP API gateway]
    Gateway --> Scope{Has inference proxy scope}
    Scope -- no --> Deny[403 structured denial]
    Scope -- yes --> Proxy[Flow Memory proxy]
    Proxy --> Warning[streaming_not_implemented warning when requested]
    Proxy --> Usage[Usage record]
    Proxy --> Audit[Inference audit chain]
```

## Checkpoint 2026-05-26 Demand and price intelligence aliases

Files changed:

- `src/flow_memory/inference_market/service.py`
- `src/flow_memory/api/marketplace_endpoints.py`
- `src/flow_memory/api/router.py`
- `src/flow_memory/api/manifest.py`
- `docs/API_SNAPSHOT.json`
- `docs/openapi/flow-memory.openapi.json`
- `docs/INFERENCE_MARKET.md`
- `tests/test_inference_capacity_futures_markets.py`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py tests/test_api_openapi_snapshot.py tests/test_api_snapshot.py tests/test_compute_market_naming.py -q`
- `python -m ruff check src/flow_memory/inference_market/service.py src/flow_memory/api/marketplace_endpoints.py src/flow_memory/api/router.py src/flow_memory/api/manifest.py tests/test_inference_capacity_futures_markets.py`
- `python -m mypy src/flow_memory/inference_market src/flow_memory/api/marketplace_endpoints.py src/flow_memory/api/manifest.py tests/test_inference_capacity_futures_markets.py --config-file pyproject.toml`
- `python scripts/check_compute_market_production.py`

Commit:

- `3babbb1 Add inference demand price intelligence`

Implementation:

- Added demand aggregation endpoints: `GET /inference/demand`, `GET /inference/demand/summary`, and `POST /inference/demand/forecast`.
- Added price intelligence endpoints: `GET /inference/prices`, `GET /inference/prices/history`, `GET /inference/prices/spreads`, `GET /inference/prices/anomalies`, and `POST /inference/prices/forecast`.
- Added deterministic summaries and forecasts so agents can inspect demand before deciding whether to buy, sell, defer, or reserve.

```mermaid
flowchart TD
    Demand[Demand snapshots] --> Summary[Demand summary]
    Summary --> DemandForecast[Demand forecast]
    Listings[Inference listings] --> PriceSnapshots[Price snapshots]
    PriceSnapshots --> History[Price history]
    History --> Spreads[Spreads]
    History --> Anomalies[Anomalies]
    History --> PriceForecast[Price forecast]
```

## Checkpoint 2026-05-26 Inference intelligence CLI

Files changed:

- `src/flow_memory/cli.py`
- `docs/INFERENCE_MARKET.md`
- `tests/test_inference_capacity_futures_markets.py`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py -q`
- `python -m ruff check src/flow_memory/cli.py tests/test_inference_capacity_futures_markets.py`
- `python -m mypy src/flow_memory/cli.py tests/test_inference_capacity_futures_markets.py --config-file pyproject.toml`
- `python scripts/check_compute_market_production.py`

Commit:

- `15f5820 Add inference intelligence CLI commands`

Implementation:

- Added inference CLI commands for demand summaries, demand forecasts, price history, price spreads, price anomalies, and price forecasts.
- Regression tests verify JSON CLI output for demand summary and price forecast.
- CLI remains dry-run and does not prompt for settlement, private keys, or provider credentials.

```mermaid
flowchart TD
    CLI[flow-memory inference] --> DemandSummary[demand-summary]
    CLI --> DemandForecast[demand-forecast]
    CLI --> PriceHistory[price-history]
    CLI --> PriceForecast[price-forecast]
    DemandSummary --> AgentDecision[Agent economic decision]
    PriceForecast --> AgentDecision
```

## Checkpoint 2026-05-26 Inference credit accounting

Files changed:

- `src/flow_memory/inference_market/service.py`
- `src/flow_memory/compute_market/storage.py`
- `src/flow_memory/compute_market/storage_backends.py`
- `docs/INFERENCE_MARKET.md`
- `tests/test_inference_capacity_futures_markets.py`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py -q`
- `python -m ruff check src/flow_memory/inference_market/service.py src/flow_memory/compute_market/storage.py src/flow_memory/compute_market/storage_backends.py tests/test_inference_capacity_futures_markets.py`
- `python -m mypy src/flow_memory/inference_market src/flow_memory/compute_market/storage.py src/flow_memory/compute_market/storage_backends.py tests/test_inference_capacity_futures_markets.py --config-file pyproject.toml`
- `python scripts/check_compute_market_production.py`

Commit:

- `3fd7cd7 Harden inference credit accounting`

Implementation:

- Inference credit buys now enforce `max_unit_price`, reject zero-fill listings, decrement listing inventory, and mark fully consumed listings filled.
- Seller inference credit balances now decrement when a matching balance exists.
- Buyer debit and seller credit ledger entries persist under the new `inference_credit_ledger_entry` record family.
- Seeded marketplace records no longer overwrite existing persisted records when a service is reconstructed against a store.

```mermaid
flowchart TD
    Buy[Buy request] --> Price[Max price guard]
    Price --> Fill[Fill calculation]
    Fill --> Inventory[Listing inventory update]
    Fill --> Balance[Seller balance update]
    Fill --> Ledger[Buyer and seller ledger entries]
    Ledger --> Store[ComputeMarketStore]
    Ledger --> Audit[Inference audit chain]
```

## Checkpoint 2026-05-26 Capacity reservation accounting

Files changed:

- `src/flow_memory/capacity_market/service.py`
- `tests/test_inference_capacity_futures_markets.py`
- `docs/CAPACITY_MARKET.md`

Tests run:

- `python -m pytest tests/test_inference_capacity_futures_markets.py -q` — 16 passed
- `python -m ruff check src/flow_memory/capacity_market/service.py tests/test_inference_capacity_futures_markets.py` — OK
- `python -m mypy src/flow_memory/capacity_market tests/test_inference_capacity_futures_markets.py --config-file pyproject.toml` — OK
- `python scripts/check_compute_market_production.py` — ruff OK, mypy OK, 427 passed, 2 skipped
- `git diff --check -- src/flow_memory/capacity_market/service.py tests/test_inference_capacity_futures_markets.py docs/CAPACITY_MARKET.md docs/ops/MULTI_DAY_BUILDOUT_STATUS.md` — clean

Commit:

- `46c5c43 Harden capacity reservation accounting`

Implementation:

- Capacity holds decrement the selected capacity window's available units and persist the updated window.
- Repeated holds and releases are idempotent, so retries cannot double-consume or double-restore simulated capacity.
- Reservation release restores available capacity once, marks the hold released, and excludes released reservations from active utilization.

```mermaid
flowchart TD
    Quote[Capacity quote] --> Hold[Dry-run hold]
    Hold --> Decrement[Decrement available units]
    Decrement --> Store[Persist capacity window]
    Hold --> Reservation[Non-binding reservation]
    Reservation --> Release[Release request]
    Release --> Restore[Restore available units once]
    Restore --> Utilization[Active utilization excludes released reservations]
```

## Checkpoint 2026-05-26 Public marketplace alpha smoke option

Files changed:

- `scripts/smoke_compute_market_public.ps1`
- `tests/test_compute_market_live_deployment.py`
- `docs/ops/PUBLIC_DEPLOYMENT_BLOCKERS.md`

Tests run:

- `python -m pytest tests/test_compute_market_live_deployment.py::test_public_smoke_script_validates_gateway_jwt_when_configured -q` — 1 passed
- `python -m ruff check tests/test_compute_market_live_deployment.py` — OK
- `python -m pytest tests/test_compute_market_live_deployment.py -q` — 49 passed
- `python scripts/check_compute_market_production.py` — ruff OK, mypy OK, 427 passed, 2 skipped
- `git diff --check -- scripts/smoke_compute_market_public.ps1 tests/test_compute_market_live_deployment.py` — clean except Git line-ending warning for the PowerShell file

Commit: `df0c3bb Add marketplace alpha public smoke option`.

Implementation:

- Public Level 1 smoke remains compute-first by default.
- Optional `-IncludeMarketAlpha` adds inference opportunity-cost, inference order-book, OpenAI-compatible proxy, capacity inventory, and futures-market checks.
- Optional marketplace alpha checks assert dry-run and no-funds safety fields instead of implying live provider, billing, settlement, or futures readiness.

```mermaid
flowchart TD
    Smoke[Public smoke script] --> Level1[Compute Level 1 gates]
    Smoke --> Optional[IncludeMarketAlpha optional flag]
    Optional --> Inference[Inference Market dry-run checks]
    Optional --> Proxy[One-line proxy dry-run check]
    Optional --> Capacity[Capacity inventory dry-run check]
    Optional --> Futures[Futures simulator non-live check]
    Futures --> Safety[No live trading or funds movement]
```

## Checkpoint 2026-05-26 Full typing evidence

Files changed:

- `docs/ops/MULTI_DAY_BUILDOUT_STATUS.md`

Tests run:

- `python -m mypy src tests scripts --config-file pyproject.toml` — OK

Commit: `95a63b2 Document full mypy evidence`.

Implementation:

- Full repository Python typing was rechecked after the latest marketplace, deployment smoke, and capacity-accounting commits.
- This updates the quality evidence from the older "legacy full-repo mypy remains failing" state to an observed passing full-repo mypy run for the current checkout.

```mermaid
flowchart TD
    Code[Current checkout] --> Mypy[Full mypy src tests scripts]
    Mypy --> Pass[No type errors observed]
    Pass --> Evidence[Quality evidence checkpoint]
```

## Checkpoint 2026-05-26 Render marketplace alpha smoke parity

Files changed:

- `scripts/deploy_compute_market_render_level1.py`
- `tests/test_compute_market_live_deployment.py`

Tests run:

- `python -m pytest tests/test_compute_market_live_deployment.py -q` — 49 passed
- `python -m ruff check scripts/deploy_compute_market_render_level1.py tests/test_compute_market_live_deployment.py` — OK
- `python -m mypy scripts/deploy_compute_market_render_level1.py tests/test_compute_market_live_deployment.py --config-file pyproject.toml` — OK
- `python scripts/check_compute_market_production.py` — ruff OK, mypy OK, 427 passed, 2 skipped

Commit: pending.

Implementation:

- Render deployment helper gained optional marketplace-alpha public smoke checks through `--include-market-alpha-smoke` or `FLOW_MEMORY_PUBLIC_SMOKE_INCLUDE_MARKET_ALPHA=true`.
- The optional smoke gate validates inference opportunity planning, inference order book, OpenAI-compatible proxy, capacity inventory, and futures markets without changing the default compute-only Level 1 gate.
- Optional checks assert dry-run, no-funds, and non-live futures safety fields.

```mermaid
flowchart TD
    RenderDeploy[Render deploy helper] --> ComputeSmoke[Compute Level 1 smoke]
    RenderDeploy --> OptionalFlag[include market alpha smoke]
    OptionalFlag --> Inference[Inference dry-run]
    OptionalFlag --> Proxy[Proxy dry-run]
    OptionalFlag --> Capacity[Capacity inventory]
    OptionalFlag --> Futures[Futures non-live]
    Futures --> Safety[Safety fields required]
```
