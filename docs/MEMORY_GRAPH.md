# Memory Graph and Governance

Status: implemented local constitutional graph with adapter seams.

## Implemented

`ConstitutionalGraph` separates memory into first-class domains:

- identity
- goals
- constraints
- strategy
- tasks
- observations
- outcomes
- reputation

Writes go through `MemoryPolicy`. Allowed and blocked writes append audit events. Blocked writes do not mutate graph state.

## Adapters

Default:

- `LocalMemoryAdapter`

Optional seams:

- `RedisMemoryAdapter`
- `QdrantMemoryAdapter`
- `Neo4jMemoryAdapter`

Optional adapters fail clearly if dependencies are not installed. They are not required for local tests.

## ODEI lesson applied

Flow Memory now treats memory as typed, policy-gated structure instead of a flat transcript. This is still local/in-memory by default, but the domain model gives production storage adapters a concrete contract.
