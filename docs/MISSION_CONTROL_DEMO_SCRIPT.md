# Mission Control Demo Script

Use this path to show real local Flow Memory state in Mission Control without GPU evidence, real funds, or external network access.

## 1. Generate a local network run

```bash
python scripts/run_local_network.py --scenario all --emit-visual-events --json-out artifacts/network/local_network_report.json
```

This creates a report with requester, worker, verifier, and observer agents plus:

- task creation,
- bid,
- assignment,
- escrow,
- work submission,
- verification,
- settlement,
- dispute/slashing,
- memory learning,
- neural advisory metadata,
- RL Arena episode metadata,
- safety approval/blocked events,
- audit events.

## 2. Export deterministic replay JSON

```bash
python scripts/export_visual_replay.py artifacts/network/local_network_report.json --out dashboard/src/mock-data/local-network-replay.json
python scripts/validate_visual_replay.py dashboard/src/mock-data/local-network-replay.json
```

The replay export stabilizes dynamic IDs and timestamps for deterministic dashboard demos.

## 3. Create demo data with one command

```bash
python scripts/mission_control_demo_data.py
```

Output summary includes `agent_count`, `event_count`, `task_count`, and the replay/report paths.

## 4. Run dashboard checks

```bash
cd dashboard
npm test
npm run build
```

The dashboard is currently dependency-light. These commands validate the checked-in Mission Control scaffold, mock data, replay controls, and mode UX.

## 5. Live local API mode

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765
```

Mission Control live mode polls:

- `GET /visual/state`
- `GET /visual/events`
- `GET /network/state`

With scopes enabled, use `visual:read` for visual state/events and `network:run` to trigger a scenario.

## Demo framing

Say: Mission Control is a public-alpha local/replay/live API visual layer for Flow Memory's human compute network.

Do not say: production hosted dashboard, mainnet payment UI, audited contract console, hardened sandbox monitor, or production ML console.
