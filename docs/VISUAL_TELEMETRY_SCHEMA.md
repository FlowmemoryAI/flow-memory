# Visual Telemetry Schema

Flow Memory Mission Control consumes `visual.telemetry.v1` events and reduces them into `VisualNetworkState`.

## Event provenance

Every visual event and state object declares one of:

- `live`: produced from an in-process local run or local API call.
- `replay`: loaded from an exported replay artifact.
- `mock`: hand-authored dashboard fallback data.
- `synthetic`: generated fixture data for tests.

Mock and replay modes must be visually labeled by the dashboard.

## Event types

- `agent`: requester, worker, verifier, observer/auditor.
- `task`: task lifecycle and status.
- `memory`: memory write/retrieval/consolidation event.
- `economy`: bid, escrow, settlement, dispute, slashing, local accounting edge.
- `neural`: backend status and advisory scores.
- `rl`: environment episode/training/benchmark signal.
- `safety`: policy/approval gate decision.
- `audit`: immutable/auditable event trail item.

## Reduced state

`VisualEvent[] -> VisualNetworkState` produces:

- `agents`
- `tasks`
- `memory`
- `economy`
- `neural`
- `rl`
- `safety`
- `audit`
- `runtime`

Every visual object carries `source_event_id` where a source event is available.
