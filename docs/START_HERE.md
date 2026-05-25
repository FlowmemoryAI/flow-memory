# Start Here: Flow Memory Public Alpha

Flow Memory is a local/testnet public alpha for launching memory-bearing AI agents with FlowLang, local economy flows, neural advisory metadata, RL Arena training, and Mission Control replay/live-state visualization.

Maturity: public alpha only. Flow Memory is not production-certified, not audited, not mainnet-ready, and does not move real funds by default.

## Fastest path on Windows PowerShell

```powershell
git clone https://github.com/FlowmemoryAI/flow-memory.git
cd flow-memory
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m flow_memory --json "Explore and report"
```

## Fastest path on Linux or macOS

```bash
git clone https://github.com/FlowmemoryAI/flow-memory.git
cd flow-memory
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m flow_memory --json "Explore and report"
```

## Developer launch paths

```bash
python scripts/launch_local_agent.py --goal "Explore and report"
python scripts/launch_flowlang_agent.py examples/flowlang_agent.flow --goal "Run the declared agent"
python scripts/launch_neural_agent.py --backend tiny_torch --goal "Explore and report"
python scripts/launch_local_agent_network.py
```

Live neural agent Launchpad:

```bash
python -m flow_memory launch agent --template live-research --neural tiny_torch --ticks 5 --emit-visual --json
python -m flow_memory launch agent --flow examples/live_research_agent.flow --ticks 5 --emit-visual --json
python -m flow_memory launch runs list --json
python -m flow_memory launch runs show <run_id> --json
python -m flow_memory launch runs replay <run_id> --json
```

## Local network + Mission Control replay

```bash
python scripts/run_local_network.py --scenario all --emit-visual-events --json-out artifacts/network/local_network_report.json
python scripts/export_visual_replay.py artifacts/network/local_network_report.json --out dashboard/src/mock-data/local-network-replay.json
python scripts/validate_visual_replay.py dashboard/src/mock-data/local-network-replay.json
```

## Dashboard scaffold

```bash
cd dashboard
npm install
npm test
npm run build
```

For an interactive Mission Control dev shell, run the dashboard in the frontend environment you choose and point live mode at:

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765
```

## Neural launch

```bash
pip install -e ".[dev,ml]"
python -m flow_memory --neural tiny_torch --json "Explore and report"
```

Torch/CUDA are optional. Neural models advise only; PolicyEngine and ApprovalGate remain authoritative.

## Local alpha evidence

```bash
python scripts/test_full_system.py --quick --json-out artifacts/full_system/quick_report.json
python scripts/test_public_alpha_launch.py
python scripts/export_public_alpha_launch_evidence.py
python scripts/verify_public_alpha_launch_evidence.py
python scripts/release_decision.py --target public-alpha-local-launch
```

GPU-gated targets remain blocked until the real RunPod artifact is imported.
