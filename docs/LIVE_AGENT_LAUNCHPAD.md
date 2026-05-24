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

## Safety and maturity

- Local neural-live agents are available.
- Neural decisions are advisory and policy-gated.
- `tiny_torch` deterministic local mode is the default smoke path.
- Optional PyTorch support is used only when installed/configured.
- GPU-gated release targets remain blocked until the real RunPod artifact is imported and verified.
- V-JEPA 2 and VideoMAE remain adapter seams.
- Compute Market/payment paths are dry-run only; no real funds are moved.
