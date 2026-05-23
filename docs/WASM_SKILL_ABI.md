# WebAssembly Skill ABI

Flow Memory should use the WebAssembly Component Model and WIT to define language-neutral sandboxed skill contracts.

WIT defines interfaces and worlds; it is not a general-purpose language and does not define behavior. That makes it a good fit for Flow Memory skill contracts: the host can require a typed ABI without caring whether the skill was written in Rust, Python compiled to Wasm, TypeScript, Go, Zig, or another component-capable language.

## Current files

Path: `wit/`

- `flow-memory-skill.wit`
- `flow-memory-agent.wit`
- `flow-memory-memory.wit`
- `flow-memory-economy.wit`

## ABI goals

The ABI should define:

- Skill metadata.
- Skill input/output.
- Memory read/write request.
- Audit event emission.
- Economic settlement request.
- Policy approval request.

## Skill ABI

`wit/flow-memory-skill.wit` defines:

- `skill-metadata`
- `skill-input`
- `skill-output`
- `audit-event`
- `policy-approval-request`
- `policy-approval-decision`
- `metadata()`
- `run(input)`
- `request-approval(request)`
- `emit-audit(event)`

This is the future unit of sandboxed skill execution. Today it is an interface file only; the Python runtime does not yet host Wasm components.

## Agent ABI

`wit/flow-memory-agent.wit` defines a future language-neutral agent runtime surface:

- `agent-manifest`
- `observation`
- `plan-step`
- `cycle-result`
- `manifest()`
- `propose-plan(observation)`
- `run-cycle(observation)`
- `request-policy-approval(request)`

## Memory ABI

`wit/flow-memory-memory.wit` defines memory operations for sandboxed components:

- `memory-read-request`
- `memory-write-request`
- `memory-record`
- `read-memory(request)`
- `write-memory(request)`
- `emit-audit(event)`

Memory writes should remain policy-gated. A Wasm component should not gain raw database access.

## Economy ABI

`wit/flow-memory-economy.wit` defines local/testnet economic operations:

- `economic-settlement-request`
- `settlement-result`
- `attestation-request`
- `request-settlement(request)`
- `create-attestation(request)`
- `request-policy-approval(request)`

Settlement modes include `none`, `local`, `base-sepolia`, and `base`. Chain modes are declaration seams until there is a hardened runtime and explicit deployment flow.

## Host enforcement requirements

A future Rust Wasm host must enforce:

1. Fuel/instruction limits.
2. Wall-clock timeouts.
3. Memory limits.
4. Capability-scoped imports.
5. Deny-by-default filesystem and network access.
6. Policy approval before unsafe permissions.
7. Audit event emission for every effectful operation.
8. Deterministic error reporting.
9. Signed component manifests.
10. Reproducible test fixtures.

## Skill lifecycle

```text
FlowLang skill declaration
  -> FlowIR SkillSpec
  -> WIT component metadata check
  -> host capability check
  -> policy approval if needed
  -> run component
  -> collect output and audit events
  -> update memory/economy only through host imports
```

## Current limitations

- The WIT files are not yet compiled by CI.
- No Wasm host is implemented in this layer.
- No signed Wasm component manifests exist yet.
- Python skill execution remains the default local path.

Status: ABI specification and interface files only.
