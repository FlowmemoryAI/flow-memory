# Mission Control Quickstart

Mission Control is the public-alpha visual operating layer for Flow Memory. It turns real local network runs into visual telemetry for agents, tasks, memory, neural advisory signals, RL episodes, safety gates, audit events, and simulated local economy flows.

Maturity: public-alpha scaffold connected to local state, replay files, and local API polling. It is not a hosted production dashboard.

## 1. Generate real local network visual events

```bash
python scripts/run_local_network.py --scenario all --emit-visual-events --json-out artifacts/network/local_network_report.json
```

The report includes requester, worker, verifier, and auditor agents; economy settlement; dispute/slashing; memory events; RL Arena training metadata; safety approval events; Compute Market dry-run telemetry; and neural-live advisory/session metadata when available.

## 2. Export replay data for the dashboard

```bash
python scripts/export_visual_replay.py artifacts/network/local_network_report.json --out dashboard/src/mock-data/local-network-replay.json
python scripts/validate_visual_replay.py dashboard/src/mock-data/local-network-replay.json
```

Replay JSON includes explicit `provenance = replay`. V2 reducer behavior keeps task lifecycle state deterministic: late duplicate or lower-priority events cannot regress a task from `settled` or `slashed` to an earlier state.

## 2b. Generate a live neural agent launch replay

```bash
python -m flow_memory launch agent --template mission-control-demo --neural tiny_torch --ticks 5 --emit-visual --out dashboard/src/mock-data/live-neural-agent-launch.json --json
```

This replay focuses on a single live local neural agent and includes neural session creation, perception, prediction, plan/risk scoring, policy gate application, learning ticks, memory writes, metadata-only checkpointing, and session completion.

## 2c. Generate or inspect Live Agent Operations replay

```bash
python -m flow_memory launch agent --template mission-control-demo --neural tiny_torch --ticks 3 --emit-visual --out dashboard/src/mock-data/live-agent-operations.json --json
python -m flow_memory launch runs list --json
python -m flow_memory launch runs replay <run_id> --json
python -m flow_memory launch runs export <run_id> --out artifacts/launch/bundles/<run_id>.json --json
```

The operations replay is backed by a local run record under `artifacts/launch/runs/`; it is not a background process manager or hosted telemetry service.

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
- `POST /neural/live/sessions`
- `POST /neural/live/sessions/{session_id}/step`

- `GET /launch/runs`
- `GET /launch/runs/{run_id}`
- `POST /launch/runs/{run_id}/replay`
- `POST /launch/runs/{run_id}/export`
- `POST /launch/runs/{run_id}/stop`
With local auth/scopes:

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765 --api-key dev-local-only --require-scopes
```

Read visual endpoints with `x-flow-memory-scopes: visual:read`; run network scenarios with `x-flow-memory-scopes: network:run`.

## 4. Run dashboard checks

```bash
cd dashboard
npm install
npm test
npm run build
npm run dev
```

For local development, run a frontend dev server around the existing TypeScript dashboard scaffold and choose one mode:

- `mock`: clearly labeled fallback data.
- `replay`: generated `dashboard/src/mock-data/local-network-replay.json`.
- `live`: polling the local API server.

## Visual semantics

- Blue: memory flow.
- Violet: neural advisory and prediction signals.
- Gold: economy, escrow, settlement.
- Orange/red: safety, dispute, slashing.
- Green: verification success.
- Gray: replay/mock/inactive state.

Neural/RL signals are advisory only. PolicyEngine and ApprovalGate remain authoritative.

## Live Agent Supervisor replay

Generate a supervised neural-live replay:

```bash
python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --ticks 5 --tick-interval-ms 10 --emit-visual --json
python -m flow_memory launch supervisor status --json
python -m flow_memory launch supervisor heartbeat <run_id> --json
```

Mission Control can load the stable supervisor fixture:

```text
dashboard/src/mock-data/live-agent-supervisor.json
```

Supervisor telemetry maps to the visual `supervisor` state collection and includes run id, supervisor id, agent id, backend, status, phase, tick count, last heartbeat, and policy gate state.
