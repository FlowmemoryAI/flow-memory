# Predictive Cognitive Core

Flow Memory now has a deterministic local cognition layer for prediction-driven agents.

The purpose is narrow and testable: before an agent acts, it records what it expects to happen; after observation, it compares the prediction with the actual result, computes prediction error, and writes a reusable experience record.

It does not imply AGI, awareness, emotion, unbounded autonomy, or broad future knowledge. Predictions are scoped to observable Flow Memory domains such as repo/build state, dashboard state, release evidence, agent runs, policy gates, compute-market simulations, memory retrieval, and user corrections.

## Loop

```text
perceive -> encode state -> retrieve similar experiences -> generate candidate actions
-> predict outcomes -> simulate counterfactuals -> score risk/confidence/reward
-> apply policy gate -> observe actual result -> compute prediction error
-> write experience -> store lesson -> emit Mission Control telemetry
```

Neural scoring is advisory. `PolicyEngine` and `ApprovalGate` remain authoritative.

## Local CLI

Prediction without writing an experience:

```powershell
python -m flow_memory cognition predict --goal "fix Mission Control dashboard" --action "kill port 4173 and restart npm run dev" --json
```

One prediction-driven tick with an experience record:

```powershell
python -m flow_memory cognition tick --agent live-research --goal "verify dashboard is serving real Mission Control" --json
```

Experience memory:

```powershell
python -m flow_memory cognition experiences list --json
python -m flow_memory cognition experiences show <experience_id> --json
python -m flow_memory cognition prediction-errors list --json
```

Benchmark and lesson commands:

```powershell
python -m flow_memory cognition benchmark run --scenario dashboard-stale-server --trials 5 --json
python -m flow_memory cognition benchmark run --scenario all --trials 5 --json
python -m flow_memory cognition lessons consolidate --json
python -m flow_memory cognition lessons list --json
python -m flow_memory cognition metrics --json
```

Supervised launch metadata with predictive cognition enabled:

```powershell
python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --predictive-core --ticks 5 --emit-visual --json
```

Artifacts are written under:

```text
artifacts/cognition/experiences/
artifacts/cognition/lessons/
artifacts/cognition/benchmarks/
```

Each record includes world state, retrieved memories, candidate actions, selected action, prediction, policy decision, actual outcome, prediction error, lesson, confidence/risk movement, and local deterministic learning metadata.

## Local API

Read-only prediction:

```text
POST /cognition/predict
```

Run one bounded local cognition tick:

```text
POST /cognition/tick
```

Experience and error inspection:

```text
GET /cognition/experiences
GET /cognition/experiences/{experience_id}
GET /cognition/prediction-errors
POST /cognition/memory/query
GET /launch/console/runs/{run_id}/predictions
GET /visual/embodiment/{run_id}/cognition
```

Predictive learning endpoints:

```text
POST /cognition/benchmarks/run
GET /cognition/benchmarks
GET /cognition/benchmarks/{benchmark_id}
POST /cognition/lessons/consolidate
GET /cognition/lessons
GET /cognition/lessons/{lesson_id}
GET /cognition/metrics
```

Scopes:

```text
cognition:read
cognition:run
cognition:write
```

## FlowLang

```flow
agent PredictiveResearchAgent {
  goal: "verify and improve the local Flow Memory launch state"

  neural {
    enabled: true
    backend: "tiny_torch"
    live_mode: true
    learning_enabled: true
    telemetry_enabled: true
    policy_fallback: "fail_closed"
  }

  cognition {
    predictive_core_enabled: true
    world_model: "local-deterministic"
    prediction_horizons: ["immediate", "short", "medium"]
    counterfactuals_enabled: true
    max_counterfactuals: 4
    prediction_error_learning: true
    experience_memory_enabled: true
    retrieve_similar_experiences: true
    memory_consolidation_enabled: true
    predictive_benchmarks_enabled: true
    confidence_calibration_enabled: true
    explain_predictions: true
  }

  policy {
    autonomy: "supervised"
    requires_approval: true
  }
}
```

## Mission Control

The dashboard fixture is:

```text
dashboard/src/mock-data/predictive-cognitive-core.json
```

The predictive learning fixture is:

```text
dashboard/src/mock-data/predictive-learning-benchmark.json
```

Mission Control renders a Predictive Cognition panel showing:

- current state summary
- retrieved memories
- candidate actions
- counterfactual predictions
- confidence, risk, reward, and prediction error
- selected action
- policy gate result
- actual outcome
- lesson learned
- experience record id
- learning update metadata

The panel is read-only. Replay/mock mode works without the local API, and local API mode remains optional.
The Predictive Learning panel shows benchmark scenario, trial count, prediction accuracy before/after, prediction error before/after, consolidated lessons, lesson reuse, repeated mistakes reduced, unsafe recommendations avoided, policy overrides, experience records written, selected lesson details, and trend rows.

## Public-alpha limits

- No real funds.
- No private keys.
- No transaction broadcast.
- No live settlement.
- No live provider calls.
- No unsafe write/control endpoints are exposed in the dashboard.
- GPU evidence is imported and verified as release evidence, not as production ML certification.
- Predictions are confidence-scored hypotheses that must be verified against actual observations.
- Predictive learning benchmark results are deterministic local measurements, not broad external forecasts.
