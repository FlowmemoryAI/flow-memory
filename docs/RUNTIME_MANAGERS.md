# Runtime Managers

Status: implemented local runtime layer.

Flow Memory v2 introduces runtime managers for subsystem lifecycle and health without requiring external services.

## Managers

- `AgentRuntimeManager`
- `SkillRuntimeManager`
- `MemoryRuntimeManager`
- `EconomyRuntimeManager`
- `PolicyRuntimeManager`
- `MarketplaceRuntimeManager`
- `SwarmRuntimeManager`
- `VerificationRuntimeManager`

Every manager exposes:

- `start()`
- `stop()`
- `status()`
- `health()`
- `tick()`
- `handle_event()`

`RuntimeOrchestrator` registers managers, starts/stops/ticks them, emits hash-chained `RuntimeEvent` records, and returns health summaries.

## Boundary

This is not a distributed runtime manager yet. It is a local orchestrator and typed health surface that future process supervisors, API servers, CLI commands, or dashboards can drive.
