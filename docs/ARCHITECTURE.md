# Flow Memory Architecture

Flow Memory is a local-first cognitive agent operating system with an autonomous-agent-economy layer. The architecture is intentionally split into local implementations, functional prototypes, and explicit adapter seams so the project can evolve toward production without pretending that trained ML, hardened sandboxes, or mainnet systems already exist.

## System spine

```text
perceive -> predict -> remember -> reason -> act -> evaluate -> learn -> transact
```

The loop is implemented through `src/flow_memory/core/`, perception modules, memory modules, safety policies, action execution, and optional economy settlement. A CLI smoke path exercises the loop through `python -m flow_memory --json "Explore and report"`.

## Major subsystems

| Subsystem | Primary paths | Status | Responsibility |
| --- | --- | --- | --- |
| Core cognitive loop | `src/flow_memory/core/` | Functional prototype | Typed cycle objects, plan execution, evaluation, learning, optional settlement. |
| Perception | `src/flow_memory/perception/` | Functional prototype | Ventral semantic/entity stream, dorsal motion/geometry stream, foveation, appearance-invariant toy constraints. |
| World model | `src/flow_memory/world_model/`, `src/flow_memory/perception/world_model.py` | Adapter seam + proxy | Deterministic latent prediction/free-energy proxy and V-JEPA-compatible seam. |
| Layered memory | `src/flow_memory/memory/` | Implemented local prototype | Working, episodic, semantic, procedural, economic memory and constitutional graph. |
| Safety | `src/flow_memory/safety/`, `src/flow_memory/action/sandbox.py` | Functional prototype | Policy gating, approval decisions, hash-chained audit, subprocess sandbox, rate limits, circuit breaker. |
| Runtime managers | `src/flow_memory/runtime/` | Implemented local runtime | Manager lifecycle, health, event handling, orchestrator coordination. |
| Skills | `src/flow_memory/skills/` | Implemented local runtime | Skill manifests, registry, scheduler, runner, quality evaluation, repair planning, built-ins. |
| Economy V2 | `src/flow_memory/economy/` | Implemented local emulator | DID, mock wallet, marketplace, escrow, settlement, disputes, slashing, attestations, treasury, reputation. |
| Swarm | `src/flow_memory/swarm/` | Implemented local prototype | Agent cards, discovery, delegation, coalition formation, verification, local bus. |
| API | `src/flow_memory/api/` | Implemented local router | Endpoint manifest and dependency-light request router; optional FastAPI app seam. |
| Contracts | `contracts/`, `test/` | Expanded prototype | Agent-economy Solidity contracts with Foundry tests; unaudited. |
| Adapters | `src/flow_memory/adapters/`, `src/flow_memory/memory/adapters/`, `src/flow_memory/blockchain/`, `src/flow_memory/protocols/` | Adapter seams | Redis, Qdrant, Neo4j, Web3, libp2p, MCP/A2A, model adapters. |

## Cognitive loop walkthrough

1. **Perceive**: `src/flow_memory/perception/ventral_stream.py` extracts entity/semantic signals. `src/flow_memory/perception/dorsal_stream.py` extracts motion/geometry affordances and tracks invariance constraints such as temporal consistency, optical-flow invariance, depth consistency, egomotion compensation, and appearance suppression.
2. **Predict**: `src/flow_memory/world_model/predictive.py` creates a deterministic latent forecast and surprise/free-energy proxy. Heavy ML is an adapter seam, not bundled behavior.
3. **Remember**: `src/flow_memory/memory/system.py` coordinates layered memory. `src/flow_memory/memory/constitutional_graph.py` adds typed domains for identity, goals, constraints, strategy, tasks, observations, outcomes, and reputation.
4. **Reason**: `src/flow_memory/reasoning/planner.py` and core loop planning create safe local plan steps.
5. **Act**: `src/flow_memory/action/executor.py` routes actions through policy checks and tool/sandbox execution.
6. **Evaluate**: `src/flow_memory/evaluation/evaluator.py` scores cycle outcomes and surprise.
7. **Learn**: `src/flow_memory/learning/learner.py` records local learning events.
8. **Transact**: `src/flow_memory/economy/economy_v2.py` can optionally run marketplace settlement, escrow release, reputation update, dispute, and slashing flows.

## Runtime manager layer

`src/flow_memory/runtime/manager.py` defines the lifecycle contract: `start()`, `stop()`, `status()`, `health()`, `tick()`, and `handle_event()`. Specialized managers wrap that contract:

- `AgentRuntimeManager`
- `SkillRuntimeManager`
- `MemoryRuntimeManager`
- `EconomyRuntimeManager`
- `PolicyRuntimeManager`
- `MarketplaceRuntimeManager`
- `SwarmRuntimeManager`
- `VerificationRuntimeManager`

`RuntimeOrchestrator` coordinates managers and emits health summaries. Runtime events are local and auditable; no network services are required.

## Skill system

`src/flow_memory/skills/manifest.py` defines `SkillManifest` with input/output schemas, permissions, schedule, economic value, required capabilities, and risk level. `SkillRegistry`, `SkillScheduler`, `SkillRunner`, `SkillEvaluator`, provenance records, and repair planning support local skill execution. Unsafe or economic skills are surfaced for approval rather than silently executed.

## Economy V2

`src/flow_memory/economy/economy_v2.py` implements a local task lifecycle:

```text
create task -> bid -> assign -> escrow -> submit work -> verify -> settle -> reputation update -> audit
```

It also implements failure handling:

```text
bad work -> dispute -> slash -> audit
```

`escrow.py`, `dispute.py`, `attestations.py`, `slashing.py`, `settlement.py`, `treasury.py`, `pricing.py`, and `incentives.py` are local/offline primitives. No live funds or real signing keys are required.

## API architecture

`src/flow_memory/api/manifest.py` is the source of truth for endpoint groups. `src/flow_memory/api/router.py` implements in-process handlers so tests can verify behavior without launching a server. Endpoint groups cover health, runtime, agents, memory, skills, marketplace, reputation, attestations, audit, swarm, delegation, and verification. `src/flow_memory/api/app.py` exposes an optional FastAPI seam if FastAPI is installed.

## Memory governance

`src/flow_memory/memory/memory_policy.py` gates writes to constitutional graph domains. `src/flow_memory/memory/adapters/local_adapter.py` is the default working persistence seam. Redis, Qdrant, and Neo4j adapters fail clearly when optional dependencies or services are unavailable.

## Self-improvement

`src/flow_memory/self_improvement/` tracks health degradation flags, scores outputs, detects repeated failures, generates repair plans, records diagnostics, and logs proposed changes. It does not automatically modify code without safety policy and approval.

## Contracts

The Solidity suite includes agent registry, task marketplace, escrow, reputation, attestation registry, delegation registry, dispute resolver, slashing registry, capability registry, and treasury prototypes. Foundry tests pass locally, but contracts are unaudited and not production-ready.

## Dependency direction

- Core loop may use perception, memory, safety, action, evaluation, learning, and economy.
- Runtime managers coordinate subsystems but do not own their internal persistence.
- Skills may call memory/economy/safety through typed interfaces.
- API handlers call runtime/economy/swarm primitives in-process.
- Contracts are a parallel on-chain prototype and must not be treated as live deployment state.

## Adapter seams that remain intentional

- V-JEPA/VideoMAE/PyTorch model checkpoints.
- Redis/Qdrant/Neo4j production services.
- OPA external enforcement service.
- Web3/Base/ERC-4337 account abstraction.
- libp2p networking.
- MCP/A2A gateways beyond local manifests/adapters.
- Hardened sandbox isolation.
