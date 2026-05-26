# Start Here: Flow Memory Public Alpha

Flow Memory is a local/testnet public alpha for launching memory-bearing AI agents with FlowLang, local economy flows, neural advisory metadata, predictive cognition, Agent Genesis, network learning consent, Experience Graph proof records, RL Arena training, and Mission Control replay/live-state visualization.

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

Mission Control run console and demo bundle:

```bash
python -m flow_memory launch runs export <run_id> --out artifacts/launch/bundles/<run_id>.json --json
python -m flow_memory launch bundle public-alpha --out artifacts/launch/bundles/public-alpha-local-demo.json --json
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
Predictive cognition adds a local deterministic loop for prediction, counterfactual scoring, prediction-error learning, and experience memory:

```bash
python -m flow_memory cognition predict --goal "verify dashboard" --action "check mission-control route" --json
python -m flow_memory cognition tick --agent live-research --goal "verify dashboard is serving real Mission Control" --json
python -m flow_memory cognition experiences list --json
python -m flow_memory cognition benchmark run --scenario dashboard-stale-server --trials 5 --json
python -m flow_memory cognition benchmark run --scenario all --trials 5 --json
python -m flow_memory cognition lessons consolidate --json
python -m flow_memory cognition metrics --json
```

Records are stored under `artifacts/cognition/experiences/`, `artifacts/cognition/lessons/`, and `artifacts/cognition/benchmarks/` and remain scoped to observable local Flow Memory outcomes.

## Agent Genesis

Agent Genesis is the no-download first-agent path: it creates a policy-gated profile, Agent Genome, private Memory Seed, first prediction, Agent Mirror, and Agent Passport. Network learning defaults to private only; sanitized contribution is opt-in.

```bash
python -m flow_memory genesis archetypes list --json
python -m flow_memory genesis instincts list --json
python -m flow_memory genesis boundaries list --json
python -m flow_memory genesis birth --user local-user --name Mira --archetype research-builder --purpose "Help me build Flow Memory" --instinct careful --instinct builder --consent private_only --json
python -m flow_memory genesis passport show <agent_id> --json
python -m flow_memory genesis mirror show <agent_id> --json
```

A local node download is optional for private local tools, private compute, or compute contribution.

## Experience Graph + Proof of Learning

Proof of Learning turns prediction/action/outcome/lesson traces into local graph records and reputation metrics. Private payloads are excluded by default.

```bash
python -m flow_memory graph build --json
python -m flow_memory graph proofs list --json
python -m flow_memory graph reputation list --json
python scripts/release_decision.py --target public-alpha-proof-of-learning
```

Artifacts are stored under `artifacts/experience_graph/graphs/`, `artifacts/experience_graph/proofs/`, and `artifacts/experience_graph/reputation/`.



## Local alpha evidence

```bash
python scripts/test_full_system.py --quick --json-out artifacts/full_system/quick_report.json
python scripts/test_public_alpha_launch.py
python scripts/export_public_alpha_launch_evidence.py
python scripts/verify_public_alpha_launch_evidence.py
python scripts/release_decision.py --target public-alpha-local-launch
```

GPU-gated targets remain blocked until the real RunPod artifact is imported.

## Supervise a bounded live agent run

```bash
python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --ticks 5 --tick-interval-ms 10 --emit-visual --json
python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --predictive-core --ticks 5 --emit-visual --json
python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --predictive-core --consolidate-lessons --ticks 5 --emit-visual --json
python -m flow_memory launch supervisor status --json
python -m flow_memory launch supervisor heartbeat <run_id> --json
```

Supervisor runs are local-only, finite, and policy-gated.
The Mission Control run selector can load `live-neural-agent-launch`, `live-agent-operations`, `live-agent-supervisor`, `predictive-cognitive-core`, `predictive-learning-benchmark`, `agent-genesis-onboarding`, `experience-graph-proof-of-learning`, and `local-network-replay` fixtures. The public-alpha demo bundle records GPU evidence status honestly and keeps neural/predictive/genesis/proof outputs advisory.
