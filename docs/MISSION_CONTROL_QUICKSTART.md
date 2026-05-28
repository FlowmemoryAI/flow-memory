# Mission Control Quickstart

Mission Control is the public-alpha visual operating layer for Flow Memory. It turns real local network runs into visual telemetry for agents, tasks, memory, predictive cognition, Agent Genesis, Proof of Learning, neural advisory signals, RL episodes, safety gates, audit events, and simulated local economy flows.

Maturity: public-alpha scaffold connected to local state, replay files, and local API polling. It is not a hosted production dashboard.

## 1. Generate real local network visual events

```bash
python scripts/run_local_network.py --scenario all --emit-visual-events --json-out artifacts/network/local_network_report.json
```

The report includes requester, worker, verifier, and auditor agents; economy settlement; dispute/slashing; memory events; RL Arena training metadata; safety approval events; Compute Market dry-run telemetry; and neural-live advisory/session metadata when available.

## 2. Export replay data for the dashboard

```bash
python scripts/export_visual_replay.py artifacts/network/local_network_report.json --out dashboard/src/mock-data/local-network-replay.json
python scripts/validate_visual_replay.py dashboard/src/mock-data/local-network-replay.json
```

Replay JSON includes explicit `provenance = replay`. V2 reducer behavior keeps task lifecycle state deterministic: late duplicate or lower-priority events cannot regress a task from `settled` or `slashed` to an earlier state.

## 2b. Generate a live neural agent launch replay

```bash
python -m flow_memory launch agent --template mission-control-demo --neural tiny_torch --ticks 5 --emit-visual --out dashboard/src/mock-data/live-neural-agent-launch.json --json
```

This replay focuses on a single live local neural agent and includes neural session creation, perception, prediction, plan/risk scoring, policy gate application, learning ticks, memory writes, metadata-only checkpointing, and session completion.

## 2c. Generate or inspect Live Agent Operations replay

```bash
python -m flow_memory launch agent --template mission-control-demo --neural tiny_torch --ticks 3 --emit-visual --out dashboard/src/mock-data/live-agent-operations.json --json
python -m flow_memory launch runs list --json
python -m flow_memory launch runs replay <run_id> --json
python -m flow_memory launch runs export <run_id> --out artifacts/launch/bundles/<run_id>.json --json
```

The operations replay is backed by a local run record under `artifacts/launch/runs/`; it is not a background process manager or hosted telemetry service.

## 3. Run the local API server for live polling mode

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765
```

Useful endpoints:

- `GET /visual/state`
- `GET /visual/events`
- `GET /visual/schema`
- `GET /network/state`
- `POST /network/run-scenario`
- `POST /visual/replay/start`
- `POST /neural/live/sessions`
- `POST /neural/live/sessions/{session_id}/step`

- `GET /launch/runs`
- `GET /launch/runs/{run_id}`
- `POST /launch/runs/{run_id}/replay`
- `POST /launch/runs/{run_id}/export`
- `POST /launch/runs/{run_id}/stop`
- `GET /launch/console/runs`
- `GET /launch/console/runs/{run_id}`
- `GET /launch/console/fixtures`
- `POST /launch/bundles/public-alpha`
- `POST /launch/finalize/public-alpha`
- `GET /visual/embodiment/{run_id}`
- `GET /launch/console/runs/{run_id}/embodiment`
- `POST /cognition/predict`
- `POST /cognition/tick`
- `GET /cognition/experiences`
- `GET /cognition/prediction-errors`
- `GET /launch/console/runs/{run_id}/predictions`
- `GET /visual/embodiment/{run_id}/cognition`
- `POST /cognition/benchmarks/run`
- `GET /cognition/benchmarks`
- `GET /cognition/benchmarks/{benchmark_id}`
- `POST /cognition/lessons/consolidate`
- `GET /cognition/lessons`
- `GET /cognition/lessons/{lesson_id}`
- `GET /cognition/metrics`
- `GET /genesis/archetypes`
- `GET /genesis/instincts`
- `GET /genesis/boundaries`
- `POST /genesis/birth`
- `GET /genesis/agents/{agent_id}/passport`
- `GET /genesis/agents/{agent_id}/genome`
- `GET /genesis/agents/{agent_id}/mirror`
- `POST /genesis/agents/{agent_id}/teaching`
- `GET /experience-graph`
- `GET /experience-graph/agents/{agent_id}`
- `GET /proof-of-learning`
- `GET /learning-reputation`
With local auth/scopes:

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765 --api-key dev-local-only --require-scopes
```

Read visual endpoints with `x-flow-memory-scopes: visual:read`; run network scenarios with `x-flow-memory-scopes: network:run`.
Launch console read endpoints require `x-flow-memory-scopes: launch:read`; public-alpha demo bundle export requires `x-flow-memory-scopes: launch:export`.
Cognition read endpoints require `x-flow-memory-scopes: cognition:read`; cognition ticks and benchmark runs require `x-flow-memory-scopes: cognition:run cognition:write`; lesson consolidation requires `x-flow-memory-scopes: cognition:write`.
Genesis read endpoints require `x-flow-memory-scopes: genesis:read`; birth requires `x-flow-memory-scopes: genesis:create`; teaching requires `x-flow-memory-scopes: genesis:teach`; export requires `x-flow-memory-scopes: genesis:export`.
Experience Graph read endpoints require `x-flow-memory-scopes: experience-graph:read`; graph build requires `x-flow-memory-scopes: experience-graph:write`.
Public-alpha finalizer export also requires `x-flow-memory-scopes: launch:export`.

## 4. Run dashboard checks

```bash
cd dashboard
npm install
npm test
npm run build
npm run dev
```

For local development, `npm run dev` serves the real Mission Control page at `http://127.0.0.1:4173/mission-control`. It renders checked-in replay/mock fixtures without the local API: the run selector, Live Neural Agent Launch, Live Agent Operations, Live Agent Supervisor, Local Network Replay, Predictive Cognition panel, Predictive Learning Benchmark panel, Agent Genesis panel, Proof of Learning panel, Neural Embodiment panel, Live 3D Mode panel, GPU evidence status, and public-alpha finalizer status.

The dev server exposes fixture JSON and read-only page rendering only. It does not expose launch, network-run, compute, settlement, or control POST endpoints. Optional local API mode remains a separate read-only polling path through `python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765`.


## Mission Control run selector

The dashboard includes a scoped run selector for these replay/demo fixtures:

- **Live Neural Agent Launch** — `dashboard/src/mock-data/live-neural-agent-launch.json`
- **Live Agent Operations** — `dashboard/src/mock-data/live-agent-operations.json`
- **Live Agent Supervisor** — `dashboard/src/mock-data/live-agent-supervisor.json`
- **Live Neural Embodiment** — `dashboard/src/mock-data/live-neural-embodiment.json`
- **Local Network Replay** — `dashboard/src/mock-data/local-network-replay.json`
- **Predictive Cognitive Core** — `dashboard/src/mock-data/predictive-cognitive-core.json`
- **Predictive Learning Benchmark** — `dashboard/src/mock-data/predictive-learning-benchmark.json`
- **Agent Genesis** — `dashboard/src/mock-data/agent-genesis-onboarding.json`
- **Proof of Learning** — `dashboard/src/mock-data/experience-graph-proof-of-learning.json`

The selected run status card shows run id, kind, agent id, backend, status, current phase, ticks, policy gate state, risk/confidence, memory writes, visual event count, GPU evidence status, replay artifact path, and run record path.

Event category counts separate neural, policy, memory, action, supervisor, compute/economy, and audit/safety events.

## Public-alpha local demo bundle

Build a compact bundle with local demo commands, fixture references, release evidence summary, and honest limitations:

```bash
python -m flow_memory launch bundle public-alpha --out artifacts/launch/bundles/public-alpha-local-demo.json --json
python -m flow_memory launch finalize public-alpha --out release_evidence/public_alpha_launch_finalizer.json --json
```

The bundle is local-only. It does not embed secrets, model weights, private keys, provider-network calls, settlement execution, or real-funds activity.
The finalizer writes `release_evidence/public_alpha_launch_finalizer.json` with launch evidence, release decisions, Live 3D Mode readiness, neural embodiment readiness, demo-bundle status, and a check that C:\tmp backup paths are not tracked.

## Visual semantics

- Blue: memory flow.
- Violet: neural advisory and prediction signals.
- Gold: economy, escrow, settlement.
- Orange/red: safety, dispute, slashing.
- Green: verification success.
- Gray: replay/mock/inactive state.

Neural/RL signals are advisory only. PolicyEngine and ApprovalGate remain authoritative.

## Live Agent Supervisor replay

Generate a supervised neural-live replay:

```bash
python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --ticks 5 --tick-interval-ms 10 --emit-visual --json
python -m flow_memory launch supervisor status --json
python -m flow_memory launch supervisor heartbeat <run_id> --json
```

Mission Control can load the stable supervisor fixture:

```text
dashboard/src/mock-data/live-agent-supervisor.json
```

Supervisor telemetry maps to the visual `supervisor` state collection and includes run id, supervisor id, agent id, backend, status, phase, tick count, last heartbeat, and policy gate state.

## Predictive Cognition panel

Generate a local deterministic cognition record:

```bash
python -m flow_memory cognition predict --goal "verify dashboard" --action "check mission-control route" --json
python -m flow_memory cognition tick --agent live-research --goal "verify dashboard is serving real Mission Control" --json
```

Mission Control can load the stable cognition fixture:

```text
dashboard/src/mock-data/predictive-cognitive-core.json
```

The panel shows current state summary, retrieved memories, candidate actions, counterfactual predictions, selected action, policy gate result, actual outcome, prediction error, lesson learned, experience id, and local deterministic learning metadata. It is read-only and keeps predictions scoped to observable Flow Memory outcomes.

## Agent Genesis panel

Generate a local birth record through the CLI:

```bash
python -m flow_memory genesis birth --user local-user --name Mira --archetype research-builder --purpose "Help me build Flow Memory" --instinct careful --instinct builder --consent private_only --json
```

Mission Control can load the stable Agent Genesis fixture:

```text
dashboard/src/mock-data/agent-genesis-onboarding.json
```

The panel shows Agent Birth Flow, Agent Genome, Memory Seed, Learning Consent, First Prediction, Agent Mirror, Agent Passport, contribution status, and the no-download first-agent path. Network learning is private only by default; sanitized contribution requires explicit opt-in. The optional node path is for private tools, private compute, or compute contribution.

## Predictive Learning Benchmark panel

Run deterministic local benchmark scenarios and consolidate lessons:

```bash
python -m flow_memory cognition benchmark run --scenario dashboard-stale-server --trials 5 --json
python -m flow_memory cognition benchmark run --scenario all --trials 5 --json
python -m flow_memory cognition lessons consolidate --json
python -m flow_memory cognition metrics --json
```

Mission Control can load the stable predictive learning fixture:

```text
dashboard/src/mock-data/predictive-learning-benchmark.json
```

The panel shows benchmark scenario, trial count, prediction accuracy before/after, prediction error before/after, lessons consolidated, lesson reuse, repeated mistakes reduced, unsafe recommendations avoided, policy overrides, experience records written, selected lesson details, and trend rows. It is read-only and keeps lessons advisory; PolicyEngine and ApprovalGate remain authoritative.

## Proof of Learning panel

Build local graph/proof/reputation artifacts:

```bash
python -m flow_memory graph build --json
python -m flow_memory graph proofs list --json
python -m flow_memory graph reputation list --json
```

Mission Control can load the stable Proof of Learning fixture:

```text
dashboard/src/mock-data/experience-graph-proof-of-learning.json
```

The panel shows Experience Graph counts, proof records, learning reputation, graph events, and artifact paths. It is read-only, excludes private payloads, and keeps PolicyEngine and ApprovalGate authoritative.

## Neural embodiment view

Generate the 3D-ready neural embodiment fixture from the current supervisor replay:

```bash
python -m flow_memory launch visual embodiment --run live-agent-supervisor --out dashboard/src/mock-data/live-neural-embodiment.json --json
```

Local API reads expose the same projection:

```text
GET /visual/embodiment/{run_id}
GET /launch/console/runs/{run_id}/embodiment
```

The embodiment card shows the agent id, neural session id, backend, imported RunPod GPU evidence status, current loop phase, confidence/risk scores, policy gate state, memory activation count, learning ticks, action state, supervisor heartbeat, and replay artifact path. It is 3D-ready data rendered as a compact visual graph today; it does not claim AGI, sentience, unbounded autonomous operation, provider-network calls, settlement execution, or production-trained ML quality.

## Live 3D Mode

Mission Control Live 3D Mode is the read-only 3D operator view over the neural embodiment projection. It uses the `live-neural-embodiment` fixture or `/visual/embodiment/{run_id}` payload to render the local neural agent body, memory orbits, policy gate, heartbeat, confidence/risk, learning ticks, and imported GPU evidence status.

It is CSS 3D/WebGL-ready telemetry today. It does not start a hidden process, launch an agent, contact model/provider networks, move funds, broadcast transactions, execute settlement, or override PolicyEngine/ApprovalGate.

The dashboard component is:

```text
dashboard/src/components/mission-control/Live3DModePanel.tsx
```

Run finalizer evidence after refreshing the fixture:

```bash
python -m flow_memory launch finalize public-alpha --out release_evidence/public_alpha_launch_finalizer.json --json
python scripts/verify_public_alpha_launch_finalizer.py
python scripts/release_decision.py --target public-alpha-launch-finalizer
```
## Agent Internet panel

Mission Control also includes the `agent-internet-skill-network` fixture. It shows registered agent nodes, skill manifests, a skill-match recommendation, collaboration graph, shared workspace summary, reputation, MCP manifest status, x402 dry-run payment intent, and ERC-8004 export-only status.

```bash
python -m flow_memory internet agents register --agent mira --json
python -m flow_memory internet skills publish --agent mira --skill research --skill memory --json
python -m flow_memory internet skills match --agent mira --task "build an agent skill matcher" --required-skill coding --required-skill verification --json
```

The panel is read-only. It does not expose real payments, private keys, transaction broadcast, raw private memory sharing, or policy bypass controls.
