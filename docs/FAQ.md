# Flow Memory FAQ

## How do I launch an agent?

Use either path:

```bash
python -m flow_memory --json "Explore and report"
python scripts/launch_local_agent.py --goal "Explore and report"
```

## How do I launch a FlowLang agent?

```bash
python scripts/launch_flowlang_agent.py examples/flowlang_agent.flow --goal "Run the declared agent"
python -m flow_memory --flow examples/flowlang_agent.flow --json "Run the declared agent"
```

## How do I launch a neural agent?

```bash
pip install -e ".[dev,ml]"
python -m flow_memory --neural tiny_torch --json "Explore and report"
python scripts/launch_neural_agent.py --backend tiny_torch --goal "Explore and report"
```

Torch/CUDA are optional. Without Torch, the local launcher reports a clear neural skip instead of breaking the base install.

## How do neural networks fit in?

Neural models provide advisory metadata: plan scores, risk scores, memory retrieval hints, perception/world-model prototypes, and evaluation scores. PolicyEngine and ApprovalGate remain authoritative.

## How do agents learn?

They collect traces, write memories, track evaluations, improve retrieval context, train tabular policies in RL Arena, and can run tiny optional PyTorch training scripts. This is prototype/local learning, not production ML.

## Are agents paid?

In local public alpha, agents are paid with simulated local credits. The payment lifecycle models real market semantics without moving funds.

## Who pays whom?

Task requesters fund local escrow. Worker agents earn after verification. Verifier fees and treasury fees are modeled locally. Reputation is non-transferable.

## Is this using real money?

No. Real funds are disabled by default. Base Sepolia and Web3 paths are dry-run adapter seams unless an operator explicitly configures future live integrations after audit.

## Is this mainnet-ready?

No. It is local/testnet dry-run public alpha infrastructure. Contracts are unaudited and no real funds should be used.

## Is the dashboard real data or mock?

Mission Control supports three modes:

- mock: clearly labeled fallback data;
- replay: generated from real local network runs;
- live: polling the local dependency-free HTTP API server.

## How do I run Mission Control?

```bash
python scripts/run_local_network.py --scenario all --emit-visual-events --json-out artifacts/network/local_network_report.json
python scripts/export_visual_replay.py artifacts/network/local_network_report.json --out dashboard/src/mock-data/local-network-replay.json
cd dashboard
npm install
npm test
npm run build
```

Run the local API for live mode:

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765
```

## What is blocked by GPU evidence?

`neural-gpu-smoke`, `public-alpha-neural`, and GPU-dependent public launch claims remain blocked until the real RunPod artifact is imported and verified. `public-alpha-local-launch` does not require GPU evidence.
