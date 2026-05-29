# Flow Memory product thesis from the Squire / UsePod reference pattern

Squire and UsePod are reference patterns only. Flow Memory is the product and public naming surface.

## Thesis

Flow Memory should become the economic memory and decision layer for agents that need to spend, earn, defer, reserve, or simulate future compute. The first wedge is not GPU futures. The first wedge is inference credit resale and discounted inference routing.

## Product hierarchy

```mermaid
flowchart TD
    A[Flow Memory Agent Economy] --> B[Flow Memory Inference Market]
    A --> C[Flow Memory Compute Market]
    B --> D[Discounted routing]
    B --> E[Inference credit resale]
    C --> F[Jobs and provider execution]
    C --> G[Capacity routing]
    G --> H[Flow Memory Capacity Market]
    H --> I[Flow Memory Forward Capacity Market]
    I --> J[Flow Memory GPU Futures Simulator]
```

## Near-term wedge

Agents need cheaper compatible inference now. The smallest adoption step is a base URL change, not a new custody stack or regulated market.

```mermaid
flowchart LR
    SDK[Existing SDK] --> URL[Change base URL]
    URL --> Proxy[Flow Memory proxy]
    Proxy --> Policy[Spend and quality policy]
    Policy --> Market[Discounted inference market]
    Market --> Response[Compatible response]
```

## Agent buyer and seller modes

Agents can be buyers when a task has positive expected ROI. They can be sellers when unused credits have higher resale value than the expected task value.

```mermaid
flowchart TD
    Task[Agent task] --> Value[Estimate task value]
    Value --> Balance[Check credit balances]
    Balance --> Market[Check market bid and ask]
    Market --> Compare[Compare run ROI vs sell value]
    Compare --> Run[Run now]
    Compare --> Buy[Buy discounted inference]
    Compare --> Sell[Sell unused inference]
    Compare --> Defer[Defer]
    Compare --> Downgrade[Downgrade tier]
```

## Demand aggregation comes before futures

Flow Memory should record demand and price memory before simulating forward capacity or futures.

```mermaid
flowchart TD
    Requests[Inference requests] --> Demand[Demand snapshots]
    Demand --> Prices[Price history]
    Prices --> Routing[Better route selection]
    Routing --> Capacity[Capacity reservation signals]
    Capacity --> Forwards[Forward capacity simulation]
    Forwards --> Futures[GPU futures simulator]
```

## Public product layers

1. Flow Memory Inference Market
2. Flow Memory Compute Market
3. Flow Memory Capacity Market
4. Flow Memory Forward Capacity Market
5. Flow Memory GPU Futures Simulator
6. Flow Memory Agent Economy

## Explicit non-goals for this buildout

- No live settlement.
- No funds moved.
- No private keys.
- No transaction broadcast.
- No mainnet settlement.
- No live futures trading.
- No margin.
- No leverage.
- No legal, compliance, or regulatory approval claims.

## Required safety posture

Every payment, settlement, capacity reservation, forward capacity, and futures response must remain dry-run or simulation-only and expose enough fields for clients to fail closed.

```mermaid
flowchart TD
    A[Request] --> B{Unsafe terms or live mode?}
    B -->|yes| C[Reject with next safe action]
    B -->|no| D[Dry-run simulation]
    D --> E[Audit event]
    E --> F[Response with safety fields]
```

## Strategic implementation order

1. Model inference credits, listings, orders, fills, and usage.
2. Add an agent opportunity-cost planner.
3. Add `/inference/*` API and CLI.
4. Add OpenAI-compatible fake-provider proxy path.
5. Persist demand and price history.
6. Add capacity market package above existing Compute Market capacity reservations.
7. Add forward capacity simulator.
8. Add GPU futures simulator.
9. Expand OpenAPI snapshots, docs, and deployment evidence.
