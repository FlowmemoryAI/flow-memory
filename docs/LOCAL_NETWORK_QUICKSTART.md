# Local Network Quickstart

The local network runs requester, worker, verifier, and auditor agents in-process. No external network, wallet, private key, or real funds are required.

```bash
python scripts/run_local_network.py --scenario basic-economy
python scripts/run_local_network.py --scenario neural-agent
python scripts/run_local_network.py --scenario rl-training
python scripts/run_local_network.py --scenario dispute-slashing
python scripts/run_local_network.py --scenario all --json-out artifacts/network/local_network_report.json
```

Scenarios:

- `basic-economy`: requester posts a task, worker bids, local escrow settles after verification.
- `neural-agent`: worker runs with neural advisory metadata.
- `rl-training`: SafetyGateEnv trains a local tabular policy and reports before/after reward.
- `dispute-slashing`: bad work triggers dispute and local reputation penalty.

The local network is a public-alpha simulator and orchestration harness, not a production distributed network.
