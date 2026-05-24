# Agent Economy Quickstart

Run the local economy task demo:

```bash
python examples/launch_agent_economy_task_demo.py
```

Run the full local network economy scenario:

```bash
python scripts/run_local_network.py --scenario basic-economy
```

What happens:

1. Requester creates a task.
2. Worker bids.
3. Requester assigns the task.
4. Escrow locks local simulated credits.
5. Worker submits work.
6. Verifier accepts or rejects.
7. Settlement pays worker/verifier/treasury locally.
8. Reputation updates.
9. Receipts/audit records are emitted.

Default mode uses simulated credits only. Future Base Sepolia / ERC-4337 integrations are dry-run adapter seams until explicitly configured and audited.
