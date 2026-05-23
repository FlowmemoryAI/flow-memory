# Risk Taxonomy

## Technical risks

- Crashes, resource exhaustion, sandbox escape, stale memory retrieval, tool schema mismatch, model drift.
- Controls: timeouts, memory limits, least-privilege permissions, tests, audit logs, typed plans.

## Economic risks

- Fraud, theft, marketplace manipulation, reputation gaming, escrow griefing.
- Controls: non-transferable reputation, escrow state machine, human approval for value transfer, slashing hooks, audit trail.

## Social risks

- Harassment, misinformation, manipulation, privacy violations.
- Controls: policy engine, approval gates, privacy boundaries, safe default tool set, immutable action record.

## Existential or systemic risks

- Uncontrolled self-improvement, value drift, runaway automation, autonomous resource acquisition.
- Controls: no self-modification by default, no default network or wallet transfer permissions, rate limiting, circuit-breaker-ready safety facade, human-in-the-loop critical actions.
