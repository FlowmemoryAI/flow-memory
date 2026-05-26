# Neural Live Agents

Flow Memory supports **live local neural agents** as a public-alpha prototype. A live neural agent attaches an `AgentProfile` to a local neural runtime session, emits deterministic neural telemetry, and records advisory perception/prediction/plan/risk/learning metadata during the agent loop.

This is not AGI, not unbounded autonomous operation, and not V-JEPA 2 or VideoMAE execution. Neural outputs advise only. `PolicyEngine` and `ApprovalGate` remain authoritative. The RunPod RTX 4090 validation artifact is imported and verified for GPU-gated release evidence, but that is not production ML certification.

## What runs today

- Local runtime sessions with session IDs and attached agent IDs.
- `tiny_torch` backend selection with deterministic local fallback when PyTorch is unavailable and policy allows fallback.
- Optional PyTorch-backed tiny models when `flow-memory[ml]` is installed.
- Deterministic local neural step metadata:
  - perception encoding metadata
  - prediction confidence
  - plan score
  - risk score
  - neural memory candidates
  - action recommendation
  - policy gate state
- Deterministic local learning update metadata:
  - before metric
  - after metric
  - proxy loss
  - learning tick count
- Metadata-only checkpoint records.
- Mission Control visual/replay telemetry for neural live sessions.
- Predictive Cognitive Core telemetry for state encoding, counterfactual prediction, policy-gated outcome observation, prediction-error learning, and experience memory.
- Predictive learning benchmark telemetry for lesson consolidation, lesson reuse, prediction-accuracy trends, and repeated-mistake reduction in local scenarios.
- Agent Genesis telemetry for born-agent genome, private memory seed, consent mode, first prediction, mirror, passport, and optional sanitized contribution status.

## What does not run by default

- No external model/provider calls.
- No automatic checkpoint downloads.
- No raw checkpoint weights committed.
- GPU validation evidence is available only through the imported and verified RunPod release artifact; it is release evidence, not production ML certification.
- No V-JEPA 2 or VideoMAE live execution; those remain adapter seams.
- No bypass of policy, approval, or safety gates.

## CLI examples

Create one local live neural step:

```bash
python -m flow_memory neural live step --backend tiny_torch --goal "Explore and report"
```

Run a local agent with neural-live metadata attached:

```bash
python -m flow_memory --neural tiny_torch --neural-live --json "Explore and report"
```

If PyTorch is absent, the live runtime reports the backend as unavailable and either fails closed or uses deterministic non-neural fallback only when `policy_fallback=allow_non_neural` is set.


## Launchpad workflow

```bash
python -m flow_memory launch agent --template live-research --neural tiny_torch --ticks 5 --emit-visual --json
```

This high-level workflow creates a local agent, starts or attaches a neural-live session, runs deterministic local loop ticks, writes memory and checkpoint metadata, and exports replay-ready Mission Control telemetry. It is the recommended public-alpha demo path for neural-live agents.
Predictive cognition can be attached to supervised launch metadata without changing the neural safety boundary:

```bash
python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --predictive-core --ticks 5 --emit-visual --json
python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --predictive-core --consolidate-lessons --ticks 5 --emit-visual --json
```


Live Agent Operations adds a persistent local run registry around that workflow:

```bash
python -m flow_memory launch runs list --json
python -m flow_memory launch runs show <run_id> --json
python -m flow_memory launch runs replay <run_id> --json
python -m flow_memory launch runs export <run_id> --out artifacts/launch/bundles/<run_id>.json --json
python -m flow_memory launch doctor --json
```

Run records live under `artifacts/launch/runs/` and are local JSON metadata only.

Mission Control run console and demo bundle:

```bash
python -m flow_memory launch bundle public-alpha --out artifacts/launch/bundles/public-alpha-local-demo.json --json
```

The bundle references replay fixtures and run records instead of embedding large artifacts, and records imported GPU evidence status honestly.

## API examples

Create a live session:

```json
POST /neural/live/sessions
{
  "agent_id": "did:flow:local-agent",
  "config": {
    "enabled": true,
    "backend": "tiny_torch",
    "live_mode": true,
    "learning_enabled": true,
    "seed": 1337,
    "policy_fallback": "allow_non_neural",
    "telemetry_enabled": true
  }
}
```

Step the session:

```json
POST /neural/live/sessions/{session_id}/step
{
  "context": {
    "goal": "Explore and report",
    "plan_id": "local-plan"
  }
}
```

Run one deterministic local learning update:

```json
POST /neural/live/sessions/{session_id}/learn
{
  "sample": {
    "goal": "Explore and report",
    "outcome": "success"
  }
}
```
Predictive cognition API examples:

```text
POST /cognition/predict
POST /cognition/tick
GET /cognition/experiences
GET /cognition/prediction-errors
```

Predictive learning benchmark API examples:

```text
POST /cognition/benchmarks/run
GET /cognition/benchmarks
POST /cognition/lessons/consolidate
GET /cognition/lessons
GET /cognition/metrics
```

These endpoints use `cognition:read`, `cognition:run`, and `cognition:write` scopes. They keep predictions advisory and record lessons only after observed outcomes.
Benchmark execution uses `cognition:run cognition:write`; lesson consolidation uses `cognition:write`; read-only benchmark/lesson/metric inspection uses `cognition:read`.

Agent Genesis API examples:

```text
GET /genesis/archetypes
GET /genesis/instincts
GET /genesis/boundaries
POST /genesis/birth
GET /genesis/agents/{agent_id}/passport
GET /genesis/agents/{agent_id}/genome
GET /genesis/agents/{agent_id}/mirror
POST /genesis/agents/{agent_id}/teaching
```

These endpoints use `genesis:read`, `genesis:create`, `genesis:teach`, and `genesis:export` scopes. The first agent path needs no download; the optional node path is for private local tools, private compute, or compute contribution.


## FlowLang example

```flowlang
agent LiveResearchAgent {
  goal: "research and summarize local project state"

  neural {
    enabled: true
    backend: "tiny_torch"
    live_mode: true
    learning_enabled: true
    seed: 1337
    model_profile: "local-small"
    perception_streams: ["text", "events", "memory"]
    plan_scoring_enabled: true
    risk_scoring_enabled: true
    memory_retrieval_enabled: true
    telemetry_enabled: true
    policy_fallback: "allow_non_neural"
  }

  policy {
    autonomy: "supervised"
    approval_required: true
  }
}
```

## Mission Control telemetry

The visual telemetry path emits neural state suitable for Mission Control:

- `session_id`
- `phase`
- `prediction_confidence`
- `uncertainty`
- `plan_score`
- `risk_score`
- `surprise_score`
- `learning_tick_count`
- `memory_activation_count`
- `action_state`
- `policy_gate_state`

Replay and live dashboard modes can render this as a neural activity halo, policy gate state, confidence/risk panel, and learning tick count.
Predictive Cognition adds Mission Control telemetry for prediction, actual outcome, prediction error, lesson learned, selected action, and local deterministic learning metadata.
Predictive Learning adds Mission Control telemetry and fixtures for benchmark scenario, accuracy/error trends, lesson consolidation, lesson reuse, repeated mistakes reduced, unsafe recommendations avoided, and policy overrides.
Agent Genesis adds Mission Control telemetry and fixtures for Agent Genome, Memory Seed, instincts, boundaries, Learning Consent, First Prediction, Agent Mirror, Agent Passport, and private-only network learning defaults.

## Mission Control neural embodiment

Generate a visible neural embodiment replay for Mission Control:

```bash
python -m flow_memory launch visual embodiment --run live-agent-supervisor --out dashboard/src/mock-data/live-neural-embodiment.json --json
```

Read it from the local API:

```text
GET /visual/embodiment/{run_id}
GET /launch/console/runs/{run_id}/embodiment
```

The embodiment state exposes `agent_id`, `session_id`, backend, GPU evidence status, loop phase, confidence/risk scores, policy gate state, memory activations, learning ticks, action state, heartbeat state, and 3D-ready animation metadata.
Mission Control Live 3D Mode reads the same projection as read-only local/replay telemetry. It renders the neural agent body, memory orbits, policy gate, heartbeat, confidence/risk, and GPU evidence status without launching agents, contacting providers, moving funds, executing settlement, or bypassing PolicyEngine/ApprovalGate.

## Safety posture

A neural live recommendation cannot execute actions. The agent runner passes neural metadata to the planner/evaluator path, then applies the existing policy and approval gates. If the runtime is unavailable and policy is `fail_closed`, the agent cycle blocks rather than silently acting.

## Bounded supervisor

The Live Agent Supervisor adds finite local run supervision around neural-live agents:

```bash
python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --ticks 10 --tick-interval-ms 250 --emit-visual --json
python -m flow_memory launch supervisor status --json
python -m flow_memory launch supervisor heartbeat <run_id> --json
python -m flow_memory launch supervisor pause <run_id> --json
python -m flow_memory launch supervisor resume <run_id> --ticks 5 --emit-visual --json
python -m flow_memory launch supervisor stop <run_id> --json
```

The supervisor is bounded, local-only, inspectable, and policy-gated. Resume creates a continuation run from prior metadata rather than reviving a hidden process.
Mission Control can display supervisor and launchpad runs through a local run selector/status card. The selector reads replay fixtures for live neural launch, operations, supervisor, and local-network runs.
The public-alpha finalizer records Live 3D Mode readiness, neural embodiment readiness, launch evidence, demo bundle status, release decisions, and the invariant that the C:\tmp backup is not tracked.
