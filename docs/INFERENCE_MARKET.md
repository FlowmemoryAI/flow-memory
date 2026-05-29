# Flow Memory Inference Market

Flow Memory Inference Market is a dry-run marketplace layer for inference credit resale, discounted routing, demand aggregation, and agent economic decisions. Flow Memory is the product and the public naming surface.

## Architecture

```mermaid
flowchart TD
    Buyer[Agent buyer] --> Planner[Opportunity planner]
    Seller[Agent seller] --> Listings[Inference credit listings]
    Planner --> Quotes[Inference quotes]
    Listings --> Quotes
    Quotes --> Route[Selected inference route]
    Route --> Usage[Inference usage ledger]
    Usage --> Memory[Agent economic memory]
    Route --> Audit[Audit event]
```

## Demand and price intelligence

```mermaid
flowchart TD
    Demand[Buyer and agent demand] --> Snapshots[Demand snapshots]
    Snapshots --> Summary[Demand summary]
    Summary --> Forecast[Demand forecast]
    Listings[Active listings] --> Prices[Price snapshots]
    Prices --> History[Price history]
    History --> Spreads[Spread summary]
    History --> Anomalies[Anomaly scan]
    History --> PriceForecast[Price forecast]
```

## Credit accounting

```mermaid
flowchart TD
    Listing[Active credit listing] --> Buy[Dry-run buy request]
    Buy --> PriceGuard[Max unit price guard]
    PriceGuard --> Fill[Simulated fill]
    Fill --> Inventory[Listing inventory decrement]
    Fill --> Balance[Seller balance decrement]
    Fill --> Ledger[Buyer and seller ledger entries]
    Ledger --> Audit[Inference audit chain]
```

## Safety

All behavior is simulation-only until real provider, billing, legal, compliance, and security gates are satisfied.

- `dry_run_only=true`
- `funds_moved=false`
- `broadcast_allowed=false`
- `private_key_required=false`
- raw credentials rejected
- seller credentials never exposed

## Credential references

External inference providers are onboarded with `secret://inference/<provider-or-source-id>` references only. The service resolves those references to process environment variables named `FLOW_MEMORY_INFERENCE_CREDENTIAL_<SANITIZED_ID>` when strict credential resolution is enabled, for example:

- `secret://inference/src-real-provider`
- `FLOW_MEMORY_INFERENCE_CREDENTIAL_SRC_REAL_PROVIDER`

The resolved secret is never returned in API, CLI, health, quote, route, usage, or audit payloads. A verified non-local source cannot be created with a missing or unresolvable credential reference, and strict mode rejects quotes for external sources whose secret reference is not configured.

```mermaid
flowchart TD
    Source[Inference source] --> Ref[secret://inference/source-id]
    Ref --> Env[FLOW_MEMORY_INFERENCE_CREDENTIAL_SOURCE_ID]
    Env --> Status[credential_status configured true or false]
    Status --> Health[source health]
    Status --> StrictQuote[strict quote gate]
    StrictQuote --> NoSecret[secret value never emitted]
```

## Auth roles

The marketplace can be scoped by API key records or gateway JWT roles without putting every raw scope in every credential.

| Role | Granted scopes |
|---|---|
| `inference-viewer` | `inference:read` |
| `inference-planner` | `inference:read`, `inference:plan` |
| `inference-proxy` | `inference:read`, `inference:proxy` |
| `inference-buyer` | `inference:read`, `inference:buy` |
| `inference-seller` | `inference:read`, `inference:sell` |
| `inference-auditor` | `inference:read`, `inference:audit` |
| `inference-admin` | all inference marketplace scopes |

```mermaid
flowchart TD
    ApiKey[API key record] --> Roles[Inference roles]
    Jwt[Gateway JWT] --> Roles
    Roles --> Read[inference read]
    Roles --> Plan[inference plan]
    Roles --> Proxy[inference proxy]
    Roles --> BuySell[inference buy sell]
    Roles --> Audit[inference audit]
    Roles --> Admin[inference admin]
```

## Current implementation

- Package: `src/flow_memory/inference_market/`
- API adapters: `src/flow_memory/api/marketplace_endpoints.py`
- CLI: `flow-memory inference ...`, including `flow-memory inference credits list`, `flow-memory inference credits buy`, and `flow-memory inference credits sell`
- Tests: `tests/test_inference_capacity_futures_markets.py`
- Demand intelligence: `GET /inference/demand`, `GET /inference/demand/summary`, `POST /inference/demand/forecast`
- Price intelligence: `GET /inference/prices`, `GET /inference/prices/history`, `GET /inference/prices/spreads`, `GET /inference/prices/anomalies`, `POST /inference/prices/forecast`
- CLI demand intelligence: `flow-memory inference demand-summary --json`, `flow-memory inference demand-forecast --json`
- CLI price intelligence: `flow-memory inference price-history --json`, `flow-memory inference price-spreads --json`, `flow-memory inference price-forecast --json`

## Core objects

- `InferenceCreditSource`
- `InferenceCreditAccount`
- `InferenceCreditBalance`
- `InferenceCreditListing`
- `InferenceCreditOrder`
- `InferenceCreditFill`
- `InferenceCreditLedgerEntry`
- `InferenceQuote`
- `InferenceUsageRecord`
- `OpportunityCostDecision`

## Request flow

```mermaid
sequenceDiagram
    participant Agent
    participant FM as Flow Memory
    participant Market as Inference listings
    participant Provider as Fake provider
    Agent->>FM: POST /inference/opportunity-cost
    FM->>Market: Quote compatible listings
    Market-->>FM: Discounted dry-run quotes
    FM->>FM: Compare run vs sell vs defer
    FM-->>Agent: Decision plus safety fields
    Agent->>FM: POST /v1/chat/completions
    FM->>Provider: Route to fake provider by default
    Provider-->>FM: Compatible response
    FM-->>Agent: Response and usage metadata
```
