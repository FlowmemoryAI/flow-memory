# Flow Memory

Flow Memory is an open-source cognitive agent operating system for local-first autonomous agents. The current V2 build adds a tested local agent-economy runtime: runtime managers, typed skills, local marketplace/escrow/reputation flows, swarm delegation, a dependency-light API router, constitutional memory governance, safety-gated self-improvement, and expanded unaudited Solidity contracts.

## Current maturity

Flow Memory is production-shaped, not production-certified. Local/offline flows are implemented and tested. Heavy external systems remain adapter seams by design.

| Area | Status | Notes |
| --- | --- | --- |
| Cognitive loop | Functional prototype | `perceive -> predict -> remember -> reason -> act -> evaluate -> learn -> transact` works locally through `flow_memory.core` and CLI. |
| Dual-stream perception | Functional prototype | Deterministic ventral/dorsal streams and appearance-invariant dorsal constraints; no trained model checkpoint bundled. |
| Runtime managers | Implemented local runtime | Manager lifecycle, orchestrator, health, tick, event handling. |
| Skill system | Implemented local runtime | Manifest validation, registry, scheduler, runner, evaluator, repair planning, built-in starter skills. |
| Economy V2 | Implemented local emulator | Task, bid, escrow, verification, settlement, dispute, slashing, treasury, attestations, non-transferable reputation. |
| Swarm/delegation | Implemented local prototype | Agent cards, local discovery, delegation contracts, coalition heuristic, verifier, bus. |
| API surface | Implemented local router | Machine-readable endpoint manifest and dependency-light handlers; optional FastAPI app seam. |
| Memory graph/governance | Implemented local prototype | Constitutional graph domains, policy-gated writes, local adapter, optional Redis/Qdrant/Neo4j seams. |
| Safety/sandbox | Functional prototype | Policy gates, approval gate, hash-chained audit log, subprocess sandbox, rate limiter, circuit breaker; not hardened isolation. |
| Contracts | Expanded prototype | Foundry build/tests pass locally; contracts are unaudited and not deployment-ready. |
| Docker | Config validated | Compose config validates; full service build/up not required for local tests. |

## Repository layout

```text
src/flow_memory/
  action/              Safe tool execution and sandbox primitives
  api/                 Local API router, endpoint manifest, optional FastAPI app seam
  core/                Cognitive cycle types and loop orchestration
  economy/             Identity, wallet, marketplace, escrow, reputation, economy V2
  memory/              Layered memory plus constitutional graph and adapters
  perception/          Ventral/dorsal perception and foveation
  runtime/             Runtime manager layer and orchestrator
  safety/              Policies, approval, audit, rate limiting, circuit breaker
  self_improvement/    Health, diagnostics, quality scoring, repair planning
  skills/              Skill manifests, registry, scheduler, runner, built-ins
  swarm/               Agent cards, discovery, delegation, coalition, local bus
contracts/             Solidity agent-economy contracts
test/                  Foundry tests
tests/                 Python tests
examples/              Offline demos
docs/                  Architecture, safety, economy, competitors, launch docs
```

## Install from a clean checkout

PowerShell:

```powershell
cd E:\FlowMemory\flow-memory
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Git Bash:

```bash
cd /e/FlowMemory/flow-memory
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The package has no required network services or API keys for the tested local runtime.

## Validate

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m flow_memory --json "Explore and report"
bash scripts/verify.sh
forge build
forge test
docker compose config
```

Observed in this build:

- Python tests: `121 passed`
- CLI smoke test: passed
- Verification script: passed
- Foundry: `11 tests passed`
- Docker Compose config: passed

## Run demos

```powershell
.\.venv\Scripts\python.exe examples\agent_economy_v2_demo.py
.\.venv\Scripts\python.exe examples\multi_agent_marketplace_demo.py
.\.venv\Scripts\python.exe examples\runtime_manager_demo.py
.\.venv\Scripts\python.exe examples\skill_scheduler_demo.py
.\.venv\Scripts\python.exe examples\constitutional_memory_demo.py
.\.venv\Scripts\python.exe examples\local_api_demo.py
.\.venv\Scripts\python.exe examples\self_healing_demo.py
.\.venv\Scripts\python.exe examples\flowlang_compile_demo.py
```

## CLI

```powershell
.\.venv\Scripts\python.exe -m flow_memory --json "Explore and report"
```

The CLI runs a local cognitive cycle and returns JSON containing observation, perception, prediction, memory retrieval, plan, policy decision, action result, evaluation, learning, optional economic settlement, and audit-linked identifiers.

## Economy V2 lifecycle

The local economy emulator supports the tested happy path:

```text
create task -> bid -> assign -> escrow -> submit work -> verify -> settle -> reputation update -> audit
```

It also supports the tested failure path:

```text
submit bad work -> dispute -> slash -> audit
```

No real funds, real private keys, or live chain calls are used by default.

## API surface

Flow Memory exposes a local dependency-light API router in `src/flow_memory/api/router.py` and an endpoint manifest in `src/flow_memory/api/manifest.py`. Endpoint groups include health, runtime, agents, memory, skills, marketplace, reputation, attestations, audit, swarm, delegation, and verification. If FastAPI is installed, `src/flow_memory/api/app.py` exposes an ASGI app seam.

## Solidity contracts

Foundry contracts live in `contracts/` and tests live in `test/`. The suite covers registry, marketplace, escrow, reputation, attestations, delegation, dispute resolution, slashing, capability registry, and treasury behavior. These contracts are unaudited and intended for local/testnet iteration only.

## FlowLang and FlowIR

Flow Memory now includes a v0 language architecture layer:

- FlowIR dataclasses in `src/flow_memory/ir/`
- FlowLang v0 parser/compiler in `src/flow_memory/flowlang/`
- WIT ABI interface files in `wit/`
- Datalog-style policy/reputation/slashing/task/memory rules in `rules/`
- Example source at `examples/flowlang_agent.flow`
- Compile demo at `examples/flowlang_compile_demo.py`

FlowLang is not production-ready. It is a v0 specification plus dependency-free parser/prototype that compiles agent declarations into JSON-serializable FlowIR manifests.

## Documentation

Start with:

- `docs/ARCHITECTURE.md`
- `docs/AUTONOMOUS_AGENT_ECONOMY_V2.md`
- `docs/ECONOMY_V2.md`
- `docs/RUNTIME_MANAGERS.md`
- `docs/SKILLS.md`
- `docs/SWARM.md`
- `docs/MEMORY_GRAPH.md`
- `docs/SAFETY.md`
- `docs/SMART_CONTRACTS.md`
- `docs/API.md`
- `docs/competitors/COMPETITIVE_MATRIX.md`
- `FLOW_MEMORY_STATUS.md`
- `BUILD_REPORT.md`

## Honest limitations

- The sandbox is local subprocess/AST protection, not container, VM, or kernel isolation.
- Perception/world model behavior is deterministic proxy behavior, not trained V-JEPA/VideoMAE performance.
- Redis, Qdrant, Neo4j, OPA, libp2p, MCP gateway, Web3, ERC-4337, and Base deployment remain adapter seams.
- Contracts compile and pass local tests but are unaudited and not deployment-ready.
- Docker Compose config validates, but external service images are optional for local development and were not required for the test suite.
