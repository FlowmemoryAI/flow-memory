# Local Network Quickstart

The local network runs requester, worker, verifier, and observer/auditor agents in-process. It uses local accounting, local audit events, optional neural metadata, and optional RL advisory output. It does not use real funds or an external network by default.

## Run scenarios

```bash
python scripts/run_local_network.py --scenario basic-economy
python scripts/run_local_network.py --scenario neural-agent
python scripts/run_local_network.py --scenario rl-training
python scripts/run_local_network.py --scenario dispute-slashing
python scripts/run_local_network.py --scenario memory-learning
python scripts/run_local_network.py --scenario safety-approval
python scripts/run_local_network.py --scenario all --emit-visual-events --json-out artifacts/network/local_network_report.json
```

## Export for Mission Control

```bash
python scripts/export_visual_replay.py artifacts/network/local_network_report.json --out dashboard/src/mock-data/local-network-replay.json
python scripts/validate_visual_replay.py dashboard/src/mock-data/local-network-replay.json
```

## Scenario meanings

- `basic-economy`: requester posts a task, worker bids, local escrow settles after verification.
- `neural-agent`: worker receives neural advisory metadata where available, or a clear local skip.
- `rl-training`: SafetyGateEnv trains a local tabular policy and reports before/after reward.
- `dispute-slashing`: bad work triggers dispute and local reputation penalty.
- `memory-learning`: memory write/retrieval events feed a local improvement report.
- `safety-approval`: policy/approval events are emitted as authoritative safety gates.
- `all`: runs every scenario and writes a combined report plus visual replay state.

The local network is a public-alpha simulator and orchestration harness, not a production distributed network.
