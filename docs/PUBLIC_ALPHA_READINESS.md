# Public Alpha Readiness

Flow Memory is ready for **local public alpha** when local launch, FlowLang launch, neural advisory/live launch, predictive cognition, Agent Genesis, network learning consent, Experience Graph proof records, local network scenarios, Mission Control replay, RL Arena examples, API help, release evidence, and docs checks pass.

Run:

```bash
python scripts/test_full_system.py --quick --json-out artifacts/full_system/quick_report.json
python scripts/test_public_alpha_launch.py
python scripts/export_public_alpha_launch_evidence.py
python scripts/verify_public_alpha_launch_evidence.py
python scripts/finalize_public_alpha_launch.py
python scripts/verify_public_alpha_launch_finalizer.py
python scripts/release_decision.py --target local-public-alpha
python scripts/release_decision.py --target public-alpha-local-launch
python scripts/release_decision.py --target public-alpha-launch-finalizer
python scripts/release_decision.py --target public-alpha-cognition
python scripts/release_decision.py --target public-alpha-genesis
python scripts/release_decision.py --target public-alpha-proof-of-learning
python scripts/release_decision.py --target public-alpha-agent-internet
```

## Current maturity

| Area | Status |
| --- | --- |
| Local public alpha | Ready if `public-alpha-local-launch` passes. |
| Local agent launch | Implemented. |
| FlowLang launch | Implemented. |
| Neural advisory/live launch | Functional local prototype; Torch optional; neural-live runtime sessions and telemetry are local/advisory. |
| Live Agent Launchpad | Implemented for local neural-live demos; writes replay/evidence metadata and remains GPU-honest. |
| Live Agent Operations | Implemented for local run records, replay lookup, bundle export, safe completed-run stop/no-op behavior, and launch doctor checks. |
| Mission Control run console | Implemented for launchpad, operations, supervisor, and local-network replay fixture selection/status summaries. |
| Public-alpha demo bundle | Implemented as local JSON bundle with replay references, docs, commands, release evidence, GPU status, and honest limitations. |
| Mission Control Live 3D Mode | Implemented as a read-only CSS 3D/WebGL-ready view over local/replay neural embodiment telemetry; no agent launch, provider calls, settlement, or policy bypass. |
| Public Alpha Launch Finalizer | Implemented as evidence-only handoff for launch evidence, Live 3D mode, demo bundle, release decisions, and C:\tmp backup exclusion. |
| Predictive Cognitive Core | Implemented as local deterministic world-state encoding, candidate prediction, counterfactual scoring, prediction-error records, experience memory, FlowLang cognition blocks, API/CLI commands, and read-only Mission Control telemetry. |
| Predictive Learning Benchmark | Implemented as deterministic local repeated scenarios, memory consolidation, lesson reuse, before/after accuracy metrics, CLI/API commands, and Mission Control learning trend telemetry. |
| Agent Genesis + Network Learning Protocol | Implemented for no-download first-agent birth, Agent Genome, private Memory Seed, instincts, boundaries, first prediction, Agent Mirror, Agent Passport, private-only default consent, and sanitized opt-in contribution records. |
| Experience Graph + Proof of Learning | Implemented for local graph construction, proof records, learning reputation, private payload exclusion, CLI/API inspection, and Mission Control proof telemetry. |
| Agent Internet + Skill Matcher | Implemented for local agent identity registry, skill manifests, deterministic collaborator ranking, shared workspaces, project graph, reputation, MCP manifest policy gating, x402 dry-run payment intents, and ERC-8004 export-only adapter files. |
| Mission Control | Local replay/live API scaffold connected to real local state. |
| Agent economy | Local simulated accounting and lifecycle prototype. |
| RL Arena | Local prototype environments and tabular training. |
| Compute Market | Local dry-run provider/route/quote/payment-intent/settlement simulation; no settlement execution. |
| Neural GPU public alpha | Ready when `neural-gpu-smoke` and `public-alpha-neural` pass with imported RunPod evidence. |
| Base/Web3 | Dry-run only. |
| Mainnet | Not ready. |
| Contracts | Unaudited. |
| Sandbox | Not hardened. |
| Neural/RL | Prototype/advisory. |

## GPU-gated release status

The RunPod RTX 4090 artifact has been imported and verified in release evidence. GPU-gated targets may pass when the evidence bundle remains valid:

```bash
python scripts/release_decision.py --target neural-gpu-smoke
python scripts/release_decision.py --target public-alpha-neural
python scripts/release_decision.py --target public-alpha-launch
python scripts/release_decision.py --target public-alpha-launch-finalizer
```

Do not fake GPU evidence. If the release evidence directory is regenerated from a checkout without `artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz` or imported `release_evidence/gpu_runs/flow-memory-cloud-gpu-run-001`, GPU-gated launch state must be treated as blocked again.

Do not claim production certification, audited contracts, mainnet readiness, hardened sandboxing, real-funds custody, or production ML performance.

## Live Agent Supervisor readiness

Local public alpha includes a bounded Live Agent Supervisor for neural-live runs. It writes local supervisor state, heartbeat artifacts, run records, Mission Control replay telemetry, and exportable run bundles. It is finite by default, stoppable, inspectable, and policy-gated.

GPU-gated neural release targets are separate from local public alpha and depend on the imported RunPod evidence remaining verified.

## Mission Control run console readiness

Local public alpha includes a Mission Control run selector/status card over these fixtures:

- `live-neural-agent-launch`
- `live-agent-operations`
- `live-agent-supervisor`
- `local-network-replay`
- `predictive-cognitive-core`
- `predictive-learning-benchmark`
- `live-neural-embodiment`
- `agent-genesis-onboarding`
- `experience-graph-proof-of-learning`
- `agent-internet-skill-network`

Generate the local public-alpha demo bundle:

```bash
python -m flow_memory launch bundle public-alpha --out artifacts/launch/bundles/public-alpha-local-demo.json --json
```

The bundle is reference-oriented and local-only. It must keep GPU status honest, neural outputs advisory, policy gates authoritative, and real-funds/provider behavior disabled.
Predictive Cognition is also part of the local evidence path. It writes experience records under `artifacts/cognition/experiences/` and keeps predictions scoped to observable local outcomes.
Predictive Learning Benchmark is part of the local evidence path. It writes consolidated lessons under `artifacts/cognition/lessons/`, benchmark results under `artifacts/cognition/benchmarks/`, and validates that repeated local mistakes are reduced without bypassing policy.
Agent Genesis is part of the local evidence path. It writes Agent Genome, Memory Seed, consent, birth certificate, mirror, and passport artifacts under `artifacts/genesis/`; network learning remains private only unless the user opts into sanitized contribution records.
Experience Graph + Proof of Learning is part of the local evidence path. It writes graph, proof, and reputation artifacts under `artifacts/experience_graph/` and keeps private payloads excluded by default.
Agent Internet is part of the local evidence path. It writes identity, skill, match, collaboration, workspace, reputation, MCP manifest, dry-run payment-intent, and ERC-8004 export files under `artifacts/agent_internet/`; raw private memory, live settlement, private keys, and transaction broadcast remain excluded.



## Visible neural embodiment readiness

Mission Control includes a neural embodiment fixture and local API projection:

```bash
python -m flow_memory launch visual embodiment --run live-agent-supervisor --out dashboard/src/mock-data/live-neural-embodiment.json --json
```

```text
GET /visual/embodiment/{run_id}
GET /launch/console/runs/{run_id}/embodiment
```

This shows the local neural runtime/session, loop phase, confidence/risk, policy gate, memory activations, learning ticks, supervisor heartbeat, replay artifact, and imported GPU evidence status. It remains a public-alpha visual/replay layer, not AGI, sentience, settlement execution, or production ML certification.

## Predictive Cognitive Core readiness

```bash
python -m flow_memory cognition predict --goal "verify dashboard" --action "check mission-control route" --json
python -m flow_memory cognition tick --agent live-research --goal "verify dashboard is serving real Mission Control" --json
python -m flow_memory cognition prediction-errors list --json
```

The readiness invariant is prediction-first and evidence-backed: candidate actions are scored before observation, actual outcomes are recorded after observation, prediction error creates a lesson, and policy gates remain authoritative.

## Predictive Learning Benchmark readiness

```bash
python -m flow_memory cognition benchmark run --scenario dashboard-stale-server --trials 5 --json
python -m flow_memory cognition benchmark run --scenario all --trials 5 --json
python -m flow_memory cognition lessons consolidate --json
python -m flow_memory cognition metrics --json
python scripts/release_decision.py --target public-alpha-cognition
```

The readiness invariant is before/after and policy-backed: benchmark scenarios must exist, experience records must consolidate into lessons, later trials must reuse lessons, prediction error must drop, repeated mistakes must decrease, and PolicyEngine/ApprovalGate must stay authoritative.

## Agent Genesis readiness

```bash
python -m flow_memory genesis archetypes list --json
python -m flow_memory genesis birth --user local-user --name Mira --archetype research-builder --purpose "Help me build Flow Memory" --instinct careful --instinct builder --consent private_only --json
python -m flow_memory genesis passport show <agent_id> --json
python scripts/release_decision.py --target public-alpha-genesis
```

The readiness invariant is consent-backed: the first agent path needs no download, the optional node path is documented, raw private payloads are excluded by default, human teaching events become private lessons first, and sanitized network contribution requires explicit opt-in.

## Experience Graph + Proof of Learning readiness

```bash
python -m flow_memory graph build --json
python -m flow_memory graph proofs list --json
python -m flow_memory graph reputation list --json
python scripts/release_decision.py --target public-alpha-proof-of-learning
```

The readiness invariant is graph-backed and privacy-backed: prediction/action/outcome records must produce graph edges, learned lessons must produce proof records, reputation must derive from prediction quality and policy compliance, private payloads must stay excluded, and proof records must never bypass PolicyEngine or ApprovalGate.

## Mission Control Live 3D Mode and finalizer

Live 3D Mode reads the visible neural embodiment fixture and local API projection. It renders a read-only 3D operations view over run id, session id, heartbeat, confidence/risk, memory activations, learning ticks, policy gate state, and imported GPU evidence status. It does not start agents, contact providers, move funds, broadcast transactions, execute settlement, or bypass PolicyEngine/ApprovalGate.

Finalize the public-alpha handoff:

```bash
python -m flow_memory launch finalize public-alpha --out release_evidence/public_alpha_launch_finalizer.json --json
python scripts/verify_public_alpha_launch_finalizer.py
python scripts/release_decision.py --target public-alpha-launch-finalizer
```

The finalizer is evidence-only. It records the local demo bundle, public-alpha launch evidence, `public-alpha-local-launch` and GPU-backed `public-alpha-launch` decisions, Mission Control Live 3D Mode readiness, neural embodiment readiness, and the invariant that the C:\tmp backup is not tracked.

## Agent upgrade readiness

The optional BYOK and on-chain upgrade path is public-alpha ready only as a local, policy-gated, dry-run capability layer. The first agent does not require wallet/API key/funds. Evidence validates redaction, credential revocation, Base Sepolia default metadata, mainnet write disabled state, prepare/sign/relay separation, relay-disabled default behavior, and emergency stop.
