# Flow Memory

Flow Memory is an open-source autonomous AI agent operating system and local/testnet-ready agent economy prototype.

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

Flow Memory is production-shaped, not production-certified. It does not claim audited contracts, hardened sandboxing, mainnet readiness, or trained ML model performance.

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
```

Observed during the V3 build:

- Python tests: `184 passed`
- FlowLang compile demo: passed
- FlowLang runtime demo: passed
- FlowLang economy demo: passed
- CLI smoke: passed
- CLI `--flow`: passed
- deployment dry-run scripts: passed

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
- `docs/PRODUCTION_READINESS.md`
- `BUILD_REPORT.md`
- `FLOW_MEMORY_STATUS.md`

## Honest limitations

- FlowLang remains v0/prototype.
- Economy V3 is local/testnet-ready architecture, not a live funds system.
- Contracts are unaudited.
- Signing uses local development HMAC by default.
- Base Sepolia scripts produce dry-run payloads only.
- Sandbox hardening is an interface and policy layer; it is not hardened VM/container isolation.
- Protocol gateways are local/offline-safe seams, not production transports.
- Dashboard is a scaffold with mock data.
