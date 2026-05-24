# Mission Control Visual System

Mission Control V2 is the public-alpha visual layer for Flow Memory's local human compute network. It is data-mapped: visual elements come from `VisualEvent` records, reduced `VisualNetworkState`, local network reports, replay JSON, or local API polling.

It is not a fake landing-page animation. Mock mode exists only as a clearly labeled fallback.

## Data modes

| Mode | Source | Claim |
| --- | --- | --- |
| Mock | typed fallback fixtures | synthetic/demo-only |
| Replay | `dashboard/src/mock-data/local-network-replay.json` exported from a local network run | deterministic replay of local state |
| Live Local API | `/visual/state`, `/visual/events`, `/network/state` | local polling against the dependency-free API server |

## Visual field mappings

| Visual | Field source | Meaning |
| --- | --- | --- |
| Agent node size | `agent.reputation` | local non-transferable reputation / importance |
| Agent glow | `neural.plan_score`, `neural.surprise_score` | advisory neural activity |
| Risk halo | `safety.risk_level`, `safety.requires_approval` | policy and approval risk |
| Ring | `safety.requires_approval` | approval required / blocked path |
| Blue flow | `memory.importance` | memory write/retrieval/consolidation relevance |
| Gold edge | `economy.kind`, `economy.amount`, `economy.status` | local simulated bid, escrow, settlement, dispute, slashing |
| Violet arc | `neural.plan_score`, `prediction_confidence` | advisory prediction signal |
| Green event | `economy.kind=verification`, `task.status=verified|settled` | verification or settlement success |
| Orange/red shield | `safety.decision=blocked`, `task.status=disputed|slashed` | policy risk, dispute, slashing |
| Replay gray label | `state.provenance` | mock/replay/live mode provenance |

## Current dashboard structure

- `dashboard/src/app/mission-control/page.tsx` renders the main Mission Control surface.
- `dashboard/src/components/mission-control/` contains data-mapped visual primitives: agent nodes, task pulses, memory flows, economy edges, neural halos, prediction arcs, safety gates, legend, drawer, and replay controls.
- `dashboard/src/components/panels/` contains runtime, agent, neural, economy, RL, and audit panels.
- `dashboard/src/lib/visual-state.ts` contains typed visual state helpers.
- `dashboard/src/lib/api.ts` and `event-stream.ts` define local live API/polling semantics and disconnected state copy.

## Reducer correctness

The V2 reducer protects lifecycle state from replay regressions:

- `settled` and `slashed` are terminal task states.
- Duplicate or older events cannot move a task backward from `settled` to `assigned`, `created`, or similar lower-priority states.
- A later `disputed` or `slashed` state can override `settled` only when it carries an explicit source event.
- Ignored regressions are recorded in `runtime.ignored_regressions` for operator visibility.

## Limitations

- The dashboard is a dependency-light public-alpha scaffold, not a production-hosted console.
- Live mode is polling-first; SSE/WebSocket remains future work.
- The current visual layer uses CSS/TypeScript components and typed mock/replay/live structure; full Three.js/React Three Fiber rendering is future work.
- Mission Control visualizes and explains decisions. It does not authorize action. PolicyEngine and ApprovalGate remain authoritative.
