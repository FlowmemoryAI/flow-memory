# Flow Memory

Flow Memory is an open-source autonomous AI agent operating system and local/testnet public-alpha preflight prototype.

## Public alpha quickstart

Windows PowerShell:

```powershell
git clone https://github.com/FlowmemoryAI/flow-memory.git
cd flow-memory
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m flow_memory --json "Explore and report"
```

Linux/macOS:

```bash
git clone https://github.com/FlowmemoryAI/flow-memory.git
cd flow-memory
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m flow_memory --json "Explore and report"
```

Launch paths:

```bash
python scripts/launch_local_agent.py --goal "Explore and report"
python scripts/launch_flowlang_agent.py examples/flowlang_agent.flow --goal "Run the declared agent"
pip install -e ".[dev,ml]"
python scripts/launch_neural_agent.py --backend tiny_torch --goal "Explore and report"
python -m flow_memory --neural tiny_torch --neural-live --json "Explore and report"
python -m flow_memory neural live step --backend tiny_torch --goal "Explore and report"
python -m flow_memory launch agent --template live-research --neural tiny_torch --ticks 5 --emit-visual --json
python -m flow_memory launch agent --flow examples/live_research_agent.flow --ticks 5 --emit-visual --json
python -m flow_memory launch runs list --json
python -m flow_memory launch runs replay <run_id> --json
python -m flow_memory launch runs export <run_id> --out artifacts/launch/bundles/<run_id>.json --json
python scripts/run_local_network.py --scenario all --json-out artifacts/network/local_network_report.json
python scripts/run_agent_learning_loop.py
python scripts/test_full_system.py --quick --json-out artifacts/full_system/quick_report.json
python scripts/run_local_network.py --scenario all --emit-visual-events --json-out artifacts/network/local_network_report.json
python scripts/export_visual_replay.py artifacts/network/local_network_report.json --out dashboard/src/mock-data/local-network-replay.json
python scripts/validate_visual_replay.py dashboard/src/mock-data/local-network-replay.json
python -m flow_memory compute plan --goal "Use budgeted local compute routing with dry-run settlement"
```

Neural, neural-live, RL, and compute-market signals advise. Policy and approval gates remain authoritative.

Mission Control visual path:

```bash
python scripts/run_local_network.py --scenario all --emit-visual-events --json-out artifacts/network/local_network_report.json
python scripts/export_visual_replay.py artifacts/network/local_network_report.json --out dashboard/src/mock-data/local-network-replay.json
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765
cd dashboard
npm run build
npm test
```

Mission Control is connected to local state/replay/API data, with mock fallback clearly labeled.

The project now combines:

- FlowLang v0 agent declarations
- FlowIR manifests
- first-class AI agent profiles/state/goals/planning/execution
- layered memory and constitutional memory governance
- safe skill/tool execution seams
- local Economy V3 marketplace, escrow, settlement, disputes, slashing, reputation, receipts
- signed manifest/receipt/provenance prototypes
- SQLite durable storage
- internal API router and optional server seams
- Base Sepolia / ERC-4337 dry-run adapters
- sandbox hardening interfaces
- MCP/A2A/libp2p protocol seams
- dashboard scaffold and CI workflows
- Flow Memory Compute Market dry-run provider/route/quote/settlement simulation
- Live Agent Launchpad for one-command local neural-live agent runs and Mission Control replay artifacts
- Live Agent Operations registry for local run inspection, replay lookup, safe stop/no-op handling, and bundle export


Public-alpha RC1 preflight adds clean-clone validation, an agent reliability gauntlet, asymmetric/DID signing seams, scoped API/auth/error contracts, typed dashboard mock API client, Base Sepolia dry-run artifacts, expanded contract security tests, optional Docker sandbox backend seam, storage replay scripts, adversarial economy simulation, and hashed release evidence.
Flow Memory is production-shaped, not production-certified, not audited, and not mainnet-ready. It does not claim audited contracts, hardened sandboxing, production API authentication, safe real-funds custody, or trained ML model performance.

## Install

PowerShell:

```powershell
cd E:\FlowMemory\flow-memory
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

If no virtual environment exists:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Validate

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe examples\flowlang_compile_demo.py
.\.venv\Scripts\python.exe examples\flowlang_runtime_demo.py
.\.venv\Scripts\python.exe examples\flowlang_economy_demo.py
.\.venv\Scripts\python.exe -m flow_memory --json "Explore and report"
.\.venv\Scripts\python.exe -m flow_memory --flow examples\flowlang_agent.flow --json "Run the declared agent"
bash scripts/verify.sh
.\.venv\Scripts\python.exe scripts\generate_deployment_plan.py
.\.venv\Scripts\python.exe scripts\base_sepolia_dry_run.py
docker compose config
forge build
forge test
git diff --check
.\.venv\Scripts\python.exe scripts\public_alpha_smoke.py --root .
.\.venv\Scripts\python.exe scripts\clean_clone_validation.py --root . --out release_evidence\clean_clone_validation.json
.\.venv\Scripts\python.exe scripts\validate_base_sepolia_artifacts.py --dir deployments\base-sepolia
.\.venv\Scripts\python.exe scripts\export_event_log.py
.\.venv\Scripts\python.exe scripts\replay_event_log.py
.\.venv\Scripts\python.exe scripts\verify_storage_integrity.py
.\.venv\Scripts\python.exe scripts\sandbox_smoke_test.py
.\.venv\Scripts\python.exe scripts\release_decision.py --target public-alpha
```

Observed during the public-alpha RC1 preflight build:

- Python tests: `287 passed, 1 skipped`
- FlowLang compile demo: passed
- FlowLang runtime demo: passed
- FlowLang economy demo: passed
- CLI smoke: passed
- CLI `--flow`: passed
- deployment dry-run scripts: passed
- agent reliability gauntlet demo: passed
- adversarial economy simulation demo: passed
- clean clone validation: passed
- public-alpha release decision: passed

## Run FlowLang agent

```powershell
.\.venv\Scripts\python.exe -m flow_memory --flow examples\flowlang_agent.flow --json "Run the declared agent"
```

## Run examples

```powershell
.\.venv\Scripts\python.exe examples\agent_profile_demo.py
.\.venv\Scripts\python.exe examples\agent_economy_v3_demo.py
.\.venv\Scripts\python.exe examples\agent_dispute_slashing_demo.py
.\.venv\Scripts\python.exe examples\signed_manifest_demo.py
.\.venv\Scripts\python.exe examples\storage_persistence_demo.py
```

## Important docs

- `docs/AI_AGENT_LAYER.md`
- `docs/PUBLIC_ALPHA_QUICKSTART.md`
- `docs/LIVE_AGENT_LAUNCHPAD.md`
- `docs/NEURAL_LIVE_AGENTS.md`
- `docs/PUBLIC_ALPHA_READINESS.md`
- `docs/CLEAN_CLONE_VALIDATION.md`
- `docs/TESTNET_PREFLIGHT.md`
- `docs/RELEASE_GATES.md`
- `docs/CONTRACT_SECURITY_TESTS.md`
- `docs/DASHBOARD.md`
- `docs/AUDIT_REPLAY.md`
- `docs/ADVERSARIAL_ECONOMY_SIMULATION.md`
- `docs/AGENT_ECONOMY_V3.md`
- `docs/FLOWLANG_RUNTIME_INTEGRATION.md`
- `docs/STORAGE.md`
- `docs/SIGNED_MANIFESTS.md`
- `docs/API_SERVER.md`
- `docs/WEB3_ADAPTERS.md`
- `docs/BASE_SEPOLIA_DEPLOYMENT.md`
- `docs/SANDBOX_HARDENING.md`
- `docs/PROTOCOL_GATEWAYS.md`
- `docs/THREAT_MODEL.md`
- `docs/SQUIRE_GOAL.md`
- `docs/PRODUCTION_READINESS.md`
- `BUILD_REPORT.md`
- `FLOW_MEMORY_STATUS.md`

## Honest limitations

- FlowLang remains v0/prototype.
- Economy V3 is local/testnet-ready architecture, not a live funds system.
- Contracts are unaudited.
- Signing uses local HMAC by default plus local deterministic asymmetric seams; production key custody is not implemented.
- Base Sepolia scripts produce dry-run payloads and artifacts only.
- Sandbox hardening includes profiles, receipts, policy checks, and an optional Docker backend seam; default local sandboxing is not hardened isolation.
- Protocol gateways are local/offline-safe seams, not production transports.
- Dashboard is a typed mock API scaffold, not a live operator console.
- Compute Market integration is local dry-run planning/routing only; it does not move funds, broadcast transactions, call live providers, or imply live settlement.


## Neural Agent Layer v1

Flow Memory now includes an optional Neural Agent Layer v1 and a local neural-live runtime for public-alpha agents. The base install still has no PyTorch requirement. Install `flow-memory[ml]` to run tiny CPU-safe PyTorch prototypes for dual-stream perception, appearance-suppressed dorsal motion, tiny JEPA-style world modeling, advisory plan scoring, skill routing, risk scoring, and neural memory retrieval. Neural-live mode adds local runtime sessions, deterministic perception/prediction/plan/risk/learning telemetry, metadata-only checkpoints, and Mission Control replay signals. V-JEPA 2 and VideoMAE are adapter seams that require explicit local checkpoints; Flow Memory never downloads checkpoints automatically. Neural scores never override policy or approval gates.


## Local HTTP API server

Flow Memory now includes a dependency-free local HTTP API server for public-alpha operator testing. Run it with `python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765`. Add `--api-key dev-local-only --require-scopes` to exercise local API-key and scope gates. This is not production internet authentication; it is a local server boundary for smoke tests, demos, and preflight tools.


## Flow Arena RL + Neural Evidence RC update

This repo now includes Flow Arena, a dependency-free local RL environment layer for agent-economy decision training, plus GPU evidence import/release-gate seams. RL policies are advisory only; policy, approval, autonomy, and economy risk controls remain authoritative. Neural GPU validation evidence is stored as text/JSON metadata and hashes; raw checkpoint/model artifacts are not committed.
