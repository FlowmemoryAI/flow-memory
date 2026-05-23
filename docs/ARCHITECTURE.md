# Flow Memory Architecture

Flow Memory is a production-shaped autonomous AI agent OS prototype. The central path is:

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
| API | `src/flow_memory/api/` | Internal router, optional server seam, OpenAPI generation |
| Crypto | `src/flow_memory/crypto/` | Local HMAC signing/provenance prototype |
| Web3 | `src/flow_memory/web3/`, `scripts/base_sepolia_dry_run.py` | Base Sepolia/ERC-4337 dry-run seams |
| Dashboard | `dashboard/` | Mock-data scaffold |

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

## Boundaries and limitations

- FlowLang is not production-stable.
- Rust preflight validator is minimal; full hardened Rust runtime remains future work.
- WIT ABI exists, but no Wasm host is implemented yet.
- Sandbox profiles are not hardened isolation.
- Base Sepolia and ERC-4337 adapters are dry-run seams.
- Protocol gateways do not open network transports by default.
- Contracts are unaudited.
