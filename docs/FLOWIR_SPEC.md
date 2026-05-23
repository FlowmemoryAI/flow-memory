# FlowIR Specification

FlowIR is the intermediate representation for Flow Memory agents. FlowLang compiles into FlowIR, and future Rust/Wasm/Datalog runtimes should validate and execute FlowIR manifests.

## Design goals

- Use plain dataclasses in Python.
- Keep all fields JSON-serializable.
- Preserve safety, policy, and economy boundaries explicitly.
- Avoid depending on a specific language runtime.
- Make validation deterministic and testable.

## Current Python implementation

Path: `src/flow_memory/ir/`

| File | Responsibility |
| --- | --- |
| `agent.py` | `AgentSpec` and cross-object validation. |
| `skill.py` | `SkillSpec`. |
| `policy.py` | `PolicySpec`, `PermissionSpec`, `RiskLevel`, unsafe permission classification. |
| `plan.py` | `PlanSpec`. |
| `memory.py` | `MemorySpec`. |
| `economy.py` | `EconomicSpec`. |
| `compiler.py` | `CompileResult`, `compile_agent`, `manifest_json`. |

## Core types

### AgentSpec

Fields:

- `name: str`
- `identity: str`
- `memory: MemorySpec`
- `beliefs: tuple[str, ...]`
- `goals: tuple[str, ...]`
- `policies: tuple[PolicySpec, ...]`
- `skills: tuple[SkillSpec, ...]`
- `plans: tuple[PlanSpec, ...]`
- `economy: EconomicSpec`
- `metadata: Mapping[str, Any]`

Validation:

- Reject missing agent name.
- Validate nested specs.
- Reject duplicate policy, skill, and plan IDs.
- Reject unsafe skill permissions without covering policy.
- Reject economic settlement without identity.
- Reject plans that reference missing skills.

### SkillSpec

Fields:

- `id`
- `description`
- `permissions`
- `risk_level`
- `inputs_schema`
- `outputs_schema`
- `wasm_component`
- `metadata`

`wasm_component` is a future pointer to a Wasm Component Model artifact. It is not loaded by the Python prototype.

### PolicySpec

Fields:

- `id`
- `permissions`
- `risk_level`
- `requires_approval`
- `allow_unsafe`
- `metadata`

A policy covers a permission when the permission appears exactly in the policy permissions or when the policy contains `*`.

### PermissionSpec

Fields:

- `name`
- `description`
- `requires_approval`

### RiskLevel

Canonical values:

- `low`
- `medium`
- `high`
- `critical`

### PlanSpec

Fields:

- `id`
- `steps`
- `goal`
- `risk_level`
- `metadata`

Plan steps reference skill IDs.

### MemorySpec

Fields:

- `working_capacity`
- `episodic`
- `semantic`
- `procedural`
- `economic`
- `adapters`
- `metadata`

### EconomicSpec

Fields:

- `settlement`
- `budget`
- `currency`
- `marketplace`
- `allow_slashing`
- `metadata`

Settlement modes:

- `none`
- `local`
- `base-sepolia`
- `base`

Only `local` is implemented as a local emulator. Chain modes are declaration seams.

### CompileResult

Fields:

- `agent`
- `manifest`
- `errors`
- `warnings`

`CompileResult.ok` is true only when an agent exists and there are no errors.

## JSON manifest shape

The compiler emits a JSON-safe record:

```json
{
  "name": "FlowResearcher",
  "identity": "did:flow:researcher-001",
  "memory": {"working_capacity": 7},
  "beliefs": ["..."],
  "goals": ["..."],
  "policies": [{"id": "safe-local"}],
  "skills": [{"id": "research-brief"}],
  "plans": [{"id": "daily-research"}],
  "economy": {"settlement": "local"}
}
```

## Future host boundary

FlowIR should eventually be validated by a Rust runtime before execution. The Python prototype is authoritative for v0 tests, but not a hardened boundary.

Expected later path:

```text
FlowLang -> FlowIR JSON -> Rust validator -> Datalog policy pass -> Wasm skill host -> audit log
```

## Status

FlowIR v0 is implemented as Python dataclasses and tested. The manifest schema is not yet versioned, signed, or stabilized for third-party production use.
