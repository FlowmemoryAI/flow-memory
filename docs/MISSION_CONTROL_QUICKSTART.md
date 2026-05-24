# Mission Control Quickstart

Mission Control is the public-alpha visual operating layer for Flow Memory. It turns real local network runs into visual telemetry for agents, tasks, memory, neural advisory signals, RL episodes, safety gates, audit events, and simulated local economy flows.

Maturity: public-alpha scaffold connected to local state/replay. It is not a hosted production dashboard.

## 1. Generate real local network visual events

```bash
python scripts/run_local_network.py --scenario all --emit-visual-events --json-out artifacts/network/local_network_report.json
```

The report includes:

- requester, worker, verifier, and auditor agents
- basic economy settlement
- neural advisory metadata, or a clear torch-not-installed skip
- RL Arena safety-gate training metadata
- dispute/slashing flow
- memory-learning events
- safety approval-required event
- reduced `visual_state`

## 2. Export replay data for the dashboard

```bash
python scripts/export_visual_replay.py artifacts/network/local_network_report.json --out dashboard/src/mock-data/local-network-replay.json
```

The replay file is frontend-friendly JSON with explicit `provenance = replay`.

## 3. Run the local API server for live polling mode

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765
```

Useful endpoints:

- `GET /visual/state`
- `GET /visual/events`
- `GET /visual/schema`
- `GET /network/state`
- `POST /network/run-scenario`
- `POST /visual/replay/start`

With local auth/scopes:

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765 --api-key dev-local-only --require-scopes
```

Read visual endpoints with `x-flow-memory-scopes: visual:read`; run network scenarios with `x-flow-memory-scopes: network:run`.

## 4. Run dashboard scaffold

```bash
cd dashboard
npm install
npm run build
npm test
```

For an interactive dev server, install a React/Next shell around the existing TypeScript components. The current checked-in dashboard is intentionally dependency-light; Python validation does not require Node.

## Modes

- `mock`: clearly labeled fallback data.
- `replay`: generated local network replay JSON.
- `live`: polling the local API server.

## Visual semantics

- Blue: memory flow.
- Violet: neural advisory and prediction signals.
- Gold: economy, escrow, settlement.
- Orange/red: safety, dispute, slashing.
- Green: verification success.
- Gray: replay/mock/inactive state.

Neural/RL signals are advisory only. PolicyEngine and ApprovalGate remain authoritative.
