# Start Here: Flow Memory Public Alpha

Flow Memory is a public-alpha autonomous AI agent OS for local/testnet dry-run development. It is not production-certified, not audited, not mainnet-ready, and does not move real funds by default.

## 5-minute local launch

```bash
git clone https://github.com/FlowmemoryAI/flow-memory.git
cd flow-memory
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m flow_memory --json "Explore and report"
```

## Launch paths

```bash
python scripts/launch_local_agent.py --goal "Explore and report"
python scripts/launch_flowlang_agent.py examples/flowlang_agent.flow --goal "Run the declared agent"
python scripts/launch_neural_agent.py --backend tiny_torch --goal "Explore and report"
python scripts/launch_local_agent_network.py
python scripts/run_local_network.py --scenario all --json-out artifacts/network/local_network_report.json
python scripts/run_agent_learning_loop.py
python scripts/test_full_system.py --quick --json-out artifacts/full_system/quick_report.json
```

Neural launch uses optional advisory metadata. If Torch is not installed, the command still reports a clear local skip. PolicyEngine and ApprovalGate remain authoritative.
