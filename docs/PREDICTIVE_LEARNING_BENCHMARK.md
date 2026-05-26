# Predictive Learning Benchmark

Flow Memory now includes a deterministic local benchmark for the Predictive Cognitive Core. The benchmark proves a narrow public-alpha claim: agents can reuse consolidated lessons from prior local experiences to improve prediction accuracy in repeated, observable scenarios.

This is not AGI, not consciousness, not production autonomy, and not broad future knowledge. It measures local Flow Memory domains only: dashboard/server state, release evidence, policy gates, compute-market dry-runs, git/check outcomes, memory retrieval, and user-correction-style lessons.

## What it measures

Each trial follows the same loop:

```text
observe state -> predict outcome -> simulate allowed action -> observe actual result
-> compute prediction error -> write experience -> consolidate lesson -> retry
```

The benchmark reports:

- `prediction_accuracy_before` and `prediction_accuracy_after`
- `prediction_error_mean_before` and `prediction_error_mean_after`
- `confidence_calibration`
- `memory_retrieval_hit_rate`
- `lesson_reuse_rate`
- `unsafe_recommendation_rate`
- `policy_override_rate`
- `repeated_mistake_rate`
- `experience_count`
- `consolidated_lesson_count`

The expected public-alpha invariant is practical: repeated local trials should reuse lessons, reduce repeated mistakes, and never let lessons bypass PolicyEngine or ApprovalGate.
Agent Genesis supplies the first private memory seed and first prediction that later experience records can improve. Network learning remains private only by default; sanitized lesson contribution is opt-in and excludes raw private payloads.
Consolidated lessons and experience records can also be projected into the Experience Graph. Proof of Learning records show which prediction errors produced reusable lessons while keeping private payloads excluded.

## Scenarios

The built-in scenario registry is local and deterministic:

1. **Dashboard stale server** — learns to check port 4173, restart stale dashboard state, and verify served HTML before assuming code failed.
2. **GPU evidence import** — learns that public-alpha neural gates require imported and verified GPU evidence before export and release decisions can pass.
3. **Policy denial** — learns that useful-looking actions remain denied when policy requires approval or simulation.
4. **Compute market dry-run** — learns to use dry-run compute-market routing with no live provider calls and no funds moved.
5. **Git clean commit** — learns to run checks, stage requested paths, commit, push, and confirm a clean tree instead of assuming the tree state.

## CLI

Run one scenario:

```powershell
python -m flow_memory cognition benchmark run --scenario dashboard-stale-server --trials 5 --json
```

Run all scenarios:

```powershell
python -m flow_memory cognition benchmark run --scenario all --trials 5 --json
```

Consolidate and inspect lessons:

```powershell
python -m flow_memory cognition lessons consolidate --json
python -m flow_memory cognition lessons list --json
python -m flow_memory cognition lessons show <lesson_id> --json
```

Inspect aggregate metrics:

```powershell
python -m flow_memory cognition metrics --json
```

Build the graph/proof layer from those experiences:

```powershell
python -m flow_memory graph build --json
python -m flow_memory graph proofs list --json
python -m flow_memory graph reputation list --json
```

Supervised local launch with prediction and post-run consolidation metadata:

```powershell
python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --predictive-core --consolidate-lessons --ticks 5 --emit-visual --json
```

## API

Local API routes:

```text
POST /cognition/benchmarks/run
GET /cognition/benchmarks
GET /cognition/benchmarks/{benchmark_id}
POST /cognition/lessons/consolidate
GET /cognition/lessons
GET /cognition/lessons/{lesson_id}
GET /cognition/metrics
```

Scopes stay explicit:

```text
cognition:read
cognition:run
cognition:write
```

Benchmark execution requires `cognition:run cognition:write`. Lesson consolidation requires `cognition:write`. Metrics and lesson listing require `cognition:read`.

## Artifacts

Local records are written under:

```text
artifacts/cognition/experiences/
artifacts/cognition/lessons/
artifacts/cognition/benchmarks/
artifacts/experience_graph/graphs/
artifacts/experience_graph/proofs/
artifacts/experience_graph/reputation/
```

A consolidated lesson links back to source experience ids and stores the domain, tags, repeated error type, recommended future action, confidence/risk deltas, and usefulness score.

## Mission Control

Mission Control renders the benchmark fixture:

```text
dashboard/src/mock-data/predictive-learning-benchmark.json
```

The Predictive Learning panel shows the scenario, trial count, accuracy before/after, prediction error before/after, lessons consolidated, lessons reused, repeated mistakes reduced, unsafe recommendations avoided, policy overrides, experience records written, lesson details, and trend rows.

Replay/mock mode works without the local API. Local API mode remains optional and read-only from the dashboard surface.

## Release evidence

Release evidence is exported to:

```text
release_evidence/bundle/predictive_learning_benchmark.json
```

The evidence fails if benchmark scenarios, consolidated lessons, before/after metrics, CLI/API coverage, Mission Control fixture wiring, or public-alpha honesty invariants are missing.

## Limits

- Predictions are confidence-scored local hypotheses, not guaranteed outcomes.
- The benchmark does not predict arbitrary external events.
- Neural runtime metadata is advisory.
- PolicyEngine and ApprovalGate remain authoritative.
- No real funds, private keys, provider calls, transaction broadcasts, or settlement execution are involved.
- GPU evidence remains release evidence, not production ML certification.
