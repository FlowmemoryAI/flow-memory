# Flow Memory Architecture

Flow Memory is a production-shaped public-alpha/testnet-preflight autonomous AI agent OS prototype. The central path is:

```text
FlowLang -> FlowIR -> AgentProfile -> AgentRuntime -> cognitive loop -> memory -> skills/tools -> policy/safety -> economy -> swarm/delegation -> verification -> settlement -> reputation -> audit/event store
```

## Core layers

| Layer | Path | Status |
| --- | --- | --- |
| FlowLang | `src/flow_memory/flowlang/` | v0 parser/prototype |
| FlowIR | `src/flow_memory/ir/` | v0 dataclasses + manifest envelopes/adapters |
| AI agents | `src/flow_memory/agents/` | Functional local prototype |
| Runtime managers | `src/flow_memory/runtime/` | Local lifecycle/health/tick managers |
| Memory | `src/flow_memory/memory/`, `src/flow_memory/storage/` | Local memory + SQLite persistence |
| Skills/tools | `src/flow_memory/skills/`, `src/flow_memory/action/` | Local registry/executor + sandbox interfaces |
| Safety/policy | `src/flow_memory/safety/`, `rules/` | Local policy gates + Datalog starter rules |
| Economy V3 | `src/flow_memory/economy/economy_v3.py` | Local emulator with receipts/risk controls |
| Swarm/protocols | `src/flow_memory/swarm/`, `src/flow_memory/protocols/` | Local prototype and network adapter seams |
| API | `src/flow_memory/api/` | Internal router, optional server seam, scopes/errors/rate limits/audit middleware, OpenAPI generation |
| Crypto | `src/flow_memory/crypto/` | Local HMAC plus deterministic asymmetric/DID signing seams |
| Web3 | `src/flow_memory/web3/`, `deployments/base-sepolia/` | Base Sepolia/ERC-4337 dry-run artifacts and validators |
| Dashboard | `dashboard/` | Typed mock API scaffold |

## AI agent layer

`AgentProfile` defines identity, goals, constraints, capabilities, allowed tools/skills, memory/economy config, autonomy mode, risk budget, reputation, and metadata.

`AgentState` tracks lifecycle, current goal/plan/task graph, memory snapshot, events, approvals, marketplace tasks, delegations, health, evaluation, and errors.

`AgentRunner` executes:

1. Resolve input into goal.
2. Load memory context.
3. Generate typed plan.
4. Build task graph.
5. Check autonomy/policy.
6. Require approval when needed.
7. Execute skill/tool steps.
8. Optionally run Economy V3 settlement.
9. Evaluate output.
10. Reflect and recommend repair/consolidation.
11. Write memory and audit events.

## FlowLang integration

FlowLang source compiles to `AgentSpec`; adapters map `AgentSpec` to `AgentProfile`, skills to `SkillManifest`, policies to policy config, memory/economy to config mappings, and plans to runtime plans/task graphs.

CLI support:

```text
python -m flow_memory --flow examples/flowlang_agent.flow --json "Run the declared agent"
```

API support:

- `POST /flowlang/compile`
- `POST /flowlang/validate`
- `POST /flowlang/run`
- `GET /flowlang/examples`

## Economy V3

Economy V3 is local/testnet-ready architecture. It supports success and failure lifecycles, typed receipts, risk controls, verifier selection, non-transferable reputation, audit receipts, and memory outcome records. It does not move real funds.

## Persistence

SQLite is the default durable local store. It persists agents, agent state, goals, plans, task graphs, runtime events, audit events, skills, marketplace tasks, bids, escrows, settlements, disputes, slashing events, reputation updates, and memory records.

## Signing/provenance

Local development signing uses HMAC-SHA256 over canonical JSON. It supports manifest, receipt, DID payload, skill manifest, agent profile, and provenance hash-chain tests. Production should replace this with asymmetric DID/account signing.

## Public-alpha RC1 preflight layer

RC1 adds clean-clone validation, public-alpha smoke checks, deterministic release evidence bundles, Base Sepolia artifact validation, adversarial economy simulation, and an agent reliability gauntlet. These systems make the prototype easier to inspect and rehearse locally, but they do not convert it into production or mainnet software.

## Boundaries and limitations

- FlowLang is not production-stable.
- Rust preflight validator is minimal; full hardened Rust runtime remains future work.
- WIT ABI exists, but no Wasm host is implemented yet.
- Sandbox profiles are not hardened isolation.
- Base Sepolia and ERC-4337 adapters are dry-run seams.
- Protocol gateways do not open network transports by default.
- Contracts are unaudited.


## Neural Agent Layer v1

The architecture now includes an optional neural advisory layer: FlowLang neural config maps into `AgentProfile.neural_config`; `AgentRunner` calls `AgentNeuralBinding`; the binding attaches plan scores, skill route scores, risk scores, memory retrieval scores, and evaluation metadata. Optional `tiny_torch` modules provide dual-stream perception and tiny world-model prototypes when PyTorch is installed. Policy and approval remain authoritative.


## Flow Arena RL + Neural Evidence RC update

This repo now includes Flow Arena, a dependency-free local RL environment layer for agent-economy decision training, plus GPU evidence import/release-gate seams. RL policies are advisory only; policy, approval, autonomy, and economy risk controls remain authoritative. Neural GPU validation evidence is stored as text/JSON metadata and hashes; raw checkpoint/model artifacts are not committed.

## Local launch and learning orchestration

The launch-readiness layer adds developer-facing orchestration around the core architecture:

```text
launch script / FlowLang / API -> AgentProfile -> AgentRunner -> local network -> economy/accounting -> learning report -> release evidence
```

New local-only paths:

- `scripts/launch_local_agent.py`
- `scripts/launch_flowlang_agent.py`
- `scripts/launch_neural_agent.py`
- `scripts/run_local_network.py`
- `scripts/run_agent_learning_loop.py`
- `scripts/test_full_system.py`

`src/flow_memory/network/` coordinates requester, worker, verifier, and auditor participants in in-process scenarios. `src/flow_memory/economy/accounting.py` models simulated credits, escrow, settlement, refund, verifier fees, treasury fees, and slashing. `src/flow_memory/learning/` records traces and reports memory/RL/neural-training status.

These paths are public-alpha local orchestration and evidence tooling, not production distributed infrastructure.
