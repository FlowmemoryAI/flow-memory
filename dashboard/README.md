# Flow Memory Dashboard

This directory is the public-alpha Mission Control scaffold for Flow Memory. It is dependency-light for base validation and supports three data modes:

- `mock`: typed fallback fixtures, clearly labeled.
- `replay`: deterministic JSON exported from a real local network scenario run.
- `live`: local API polling against `/visual/state`, `/visual/events`, and `/network/state`.

## Current V2 state

- No application framework is required for the base Python test suite.
- `src/lib/types.ts` defines the dashboard snapshot model.
- `src/lib/visual-state.ts` defines Mission Control visual state and helpers for risk, neural activity, economy totals, and recent events.
- `src/lib/api.ts` defines local live API calls for `/visual/state`, `/visual/events`, and `/network/run-scenario`.
- `src/lib/event-stream.ts` defines mock/replay/live mode copy and disconnected local API UX.
- `src/lib/replay-controller.ts` supports play, pause, reset, step forward/backward, speed, timeline windows, and event filters.
- `src/app/mission-control/page.tsx` lays out the Mission Control view.
- `src/components/mission-control/` contains data-mapped visual components.
- `src/components/panels/` contains runtime, agent, economy, neural, RL, and audit panels.
- `src/mock-data/local-network-replay.json` is generated from a real local network run.

## Generate replay data

```bash
python scripts/run_local_network.py --scenario all --emit-visual-events --json-out artifacts/network/local_network_report.json
python scripts/export_visual_replay.py artifacts/network/local_network_report.json --out dashboard/src/mock-data/local-network-replay.json
python scripts/validate_visual_replay.py dashboard/src/mock-data/local-network-replay.json
```

## Local checks when Node is available

```bash
npm test
npm run build
```

The current dashboard is a local/public-alpha scaffold, not hosted production infrastructure. Future work should wrap these components in a full React/Next app, add streaming, upgrade the 3D renderer, and add signed read-only API integration before exposing it outside local development.
