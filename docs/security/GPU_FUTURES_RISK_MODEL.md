# GPU Futures Simulator risk model

The GPU Futures Simulator is simulation-only. It is not a venue for live trading, margin, leverage, collateral, or settlement.

```mermaid
flowchart TD
    Request[Futures request] --> Guard[Unsafe payload guard]
    Guard -->|unsafe| Reject[Reject]
    Guard -->|safe| Risk[Simulation risk check]
    Risk --> Mark[Mark and index price]
    Mark --> Settlement[Settlement simulation]
    Settlement --> Audit[Audit record]
```

## Prohibited live features

- live futures
- live settlement
- margin
- leverage
- collateral
- private keys
- seed phrases
- transaction signing
- transaction broadcast
- funds movement

All simulator responses must include legal and compliance review required flags.
