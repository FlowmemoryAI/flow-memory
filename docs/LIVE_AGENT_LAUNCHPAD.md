# Live Agent Launchpad

The Live Agent Launchpad is the fastest local path from a public-alpha checkout to a policy-gated neural-live Flow Memory agent. It creates an agent profile, starts a local neural runtime session, runs deterministic loop ticks, writes local memory/evidence metadata, emits Mission Control replay telemetry, and writes a replay artifact.

This is local-only public-alpha infrastructure. It does not call external models or providers, move funds, broadcast transactions, load raw model weights, or claim GPU validation.

## Fastest local command

```bash
python -m flow_memory launch agent --template live-research --neural tiny_torch --ticks 5 --emit-visual --json
```

The JSON response includes:

- `agent_id`
- `session_id`
- `backend`
- `policy_mode`
- loop tick counts
- perception/prediction/plan/risk counts
- allowed/denied action counts
- learning step count
- memory record count
- visual event count
- replay artifact path
- checkpoint metadata path
- honest GPU evidence status

## Built-in templates

- `live-research`: inspect local repo/project state and summarize it.
- `memory-scout`: retrieve and summarize relevant memory records.
- `market-observer`: simulate Compute Market routing with dry-run-only payment metadata.
- `mission-control-demo`: emit a rich replay showing neural, policy, memory, and action phases.

All templates are deterministic and local by default. `tiny_torch` is selected by default; if PyTorch is unavailable, the launchpad uses deterministic non-neural fallback only when policy explicitly allows it.

## FlowLang launch

```bash
python -m flow_memory launch agent --flow examples/live_research_agent.flow --ticks 5 --emit-visual --json
```

Other examples:

- `examples/memory_scout_agent.flow`
- `examples/market_observer_agent.flow`
- `examples/mission_control_demo_agent.flow`

Each example includes a `neural` block and a `policy` block. Neural outputs are advisory only; `PolicyEngine` and approval gates remain authoritative.

## API launch

```json
POST /launch/agent
{
  "template": "live-research",
  "ticks": 5,
  "neural": {
    "enabled": true,
    "backend": "tiny_torch",
    "live_mode": true,
    "learning_enabled": true
  },
  "emit_visual": true
}
```

FlowLang source can be launched with:

```json
POST /launch/agent/from-flow
{
  "source": "agent LiveResearchAgent { goal: \"Explore and report\" neural { enabled: true backend: \"tiny_torch\" live_mode: true policy_fallback: \"allow_non_neural\" } }",
  "ticks": 5,
  "emit_visual": true
}
```

When API scopes are enabled, these endpoints require `agents:launch`.

## Mission Control replay

Launchpad runs write replay artifacts under:

```text
artifacts/launch/live_agent_<run_id>.json
```

A stable dashboard fixture is also provided:

```text
dashboard/src/mock-data/live-neural-agent-launch.json
```

The replay includes:

- agent created
- neural session created
- backend selected
- perception encoded
- prediction generated
- plan scored
- risk scored
- policy gate applied
- action allowed or denied
- learning step completed
- memory record written
- metadata-only checkpoint written
- session completed/stopped


## Live Agent Operations

Launchpad runs now create local run records under:

```text
artifacts/launch/runs/
```

Use these commands to inspect and export completed local runs:

```bash
python -m flow_memory launch runs list --json
python -m flow_memory launch runs show <run_id> --json
python -m flow_memory launch runs replay <run_id> --json
python -m flow_memory launch runs export <run_id> --out artifacts/launch/bundles/<run_id>.json --json
python -m flow_memory launch runs stop <run_id> --json
python -m flow_memory launch doctor --json
```

`stop` is honest: completed runs return a completed/no-op result instead of pretending a background process is still alive. `resume` creates a new local continuation run from prior metadata:

```bash
python -m flow_memory launch runs resume <run_id> --ticks 3 --emit-visual --json
```

Additional FlowLang operations examples:

```bash
python -m flow_memory launch agent --flow examples/live_ops_research_agent.flow --ticks 5 --emit-visual --json
python -m flow_memory launch agent --flow examples/live_ops_memory_scout.flow --ticks 5 --emit-visual --json
python -m flow_memory launch agent --flow examples/live_ops_market_observer.flow --ticks 5 --emit-visual --json
```

A stable Mission Control operations fixture is available at:

```text
dashboard/src/mock-data/live-agent-operations.json
```

## Live Agent Supervisor

Use the bounded supervisor when you want a local run with heartbeat/status artifacts and honest pause/resume/stop controls:

```bash
python -m flow_memory launch supervisor start --template live-research --neural tiny_torch --ticks 10 --tick-interval-ms 250 --emit-visual --json
python -m flow_memory launch supervisor status --json
python -m flow_memory launch supervisor show <run_id> --json
python -m flow_memory launch supervisor heartbeat <run_id> --json
python -m flow_memory launch supervisor pause <run_id> --json
python -m flow_memory launch supervisor resume <run_id> --ticks 5 --emit-visual --json
python -m flow_memory launch supervisor stop <run_id> --json
```

Supervisor state is stored locally:

```text
artifacts/launch/supervisor/supervisor_state.json
artifacts/launch/supervisor/heartbeats/<run_id>.json
```

Resume creates a continuation run from prior metadata. It does not claim to revive an old process if no process is alive. Supervisor runs are finite by default, local-only, and policy-gated.

Supervisor FlowLang examples:

```bash
python -m flow_memory launch agent --flow examples/supervised_live_research_agent.flow --ticks 5 --emit-visual --json
python -m flow_memory launch agent --flow examples/supervised_memory_scout_agent.flow --ticks 5 --emit-visual --json
python -m flow_memory launch agent --flow examples/supervised_market_observer_agent.flow --ticks 5 --emit-visual --json
```

Mission Control supervisor fixture:

```text
dashboard/src/mock-data/live-agent-supervisor.json
```

API endpoints:

```text
POST /launch/supervisor/start
GET /launch/supervisor/status
GET /launch/supervisor/runs/{run_id}
GET /launch/supervisor/runs/{run_id}/heartbeat
POST /launch/supervisor/runs/{run_id}/pause
POST /launch/supervisor/runs/{run_id}/resume
POST /launch/supervisor/runs/{run_id}/stop
```

When API scopes are enabled, supervisor read paths require `launch:read`, start/resume require `launch:run`, and pause/stop require `launch:control`.

## Mission Control run console and demo bundle

Mission Control can inspect launchpad, operations, supervisor, and local-network replay fixtures through a run console contract. Local API read paths are:

```text
GET /launch/console/runs
GET /launch/console/runs/{run_id}
GET /launch/console/fixtures
POST /launch/bundles/public-alpha
```

When API scopes are enabled, console reads require `launch:read`; bundle export requires `launch:export`.

Build the local public-alpha demo bundle with:

```bash
python -m flow_memory launch bundle public-alpha --out artifacts/launch/bundles/public-alpha-local-demo.json --json
```

The bundle references local replay fixtures, run records, docs, release evidence, and exact demo commands. It records GPU evidence status honestly and keeps neural decisions advisory, policy-gated, and local-only.

## Safety and maturity

- Local neural-live agents are available.
- Neural decisions are advisory and policy-gated.
- `tiny_torch` deterministic local mode is the default smoke path.
- Optional PyTorch support is used only when installed/configured.
- GPU-gated release targets remain blocked until the real RunPod artifact is imported and verified.
- V-JEPA 2 and VideoMAE remain adapter seams.
- Compute Market/payment paths are dry-run only; no real funds are moved.
