# Capacity Market deployment notes

Capacity Market public deployment is gated behind the same Level 1 Compute Market infrastructure: managed Postgres, managed Redis, API key scopes, immutable audit export, and public HTTPS.

```mermaid
flowchart TD
    API[Public API] --> Auth[API key and scopes]
    Auth --> Capacity[Capacity Market simulator]
    Capacity --> Store[Managed Postgres]
    Capacity --> Redis[Managed Redis controls]
    Capacity --> Audit[Immutable audit export]
    Capacity --> Safety[Dry-run safety boundary]
```

Capacity reservations and forward capacity contracts are non-binding simulations until legal, compliance, and security review approve a future live product.
