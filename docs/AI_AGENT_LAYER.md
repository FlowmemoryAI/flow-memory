# AI Agent Layer

## Purpose

The AI agent layer is the local cognitive runtime that turns an observation into a policy-checked action cycle. It is the integration point for perception, prediction, memory, planning, safety, action execution, evaluation, learning, and local economic settlement.

## Implemented behavior

Status: implemented local prototype.

- `flow_memory.core.agent.Agent` provides the high-level facade and `Agent.create(...)` factory.
- `Agent.run_cycle(...)` delegates to `CognitiveLoop.run(...)` and returns a structured `CognitiveCycleResult`.
- The loop performs: perceive, consolidate memory, forecast, retrieve memories, generate a plan, run safety approval, execute or reject, audit the result, evaluate surprise, learn, and optionally settle economic value.
- Agent capabilities are registered as procedural skills in local memory during `Agent.create(...)`.
- The default runtime is dependency-light and in-process; no remote orchestrator is required.

## Limitations

- This is not a hardened autonomous-agent sandbox. Safety gates and subprocess controls exist, but isolation is prototype-grade.
- Model intelligence is not a trained Flow Memory model; reasoning and learning are local deterministic seams.
- Capabilities are declarations and local procedural registrations, not externally certified permissions.
- Economic settlement is local unless explicitly routed through separate unaudited contract prototypes.
- Runtime manager APIs are local process seams, not a distributed scheduler.

## Next steps

- Bind agent identities and capability manifests to signed FlowIR envelopes.
- Move high-risk execution behind a hardened runtime boundary.
- Add durable cycle/audit storage with migration support.
- Define verifier contracts for capability claims, policy decisions, and economic actions.
- Add production observability for cycle latency, rejection reasons, action outcomes, and settlement state.
