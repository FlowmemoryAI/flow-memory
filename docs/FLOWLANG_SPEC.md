# FlowLang v0 Specification

FlowLang is Flow Memory's cognitive agent DSL. Its job is to describe an agent's identity, memory, beliefs, goals, policies, skills, plans, and economic settings in a human-readable format that compiles into FlowIR.

FlowLang v0 is intentionally small. It is a parser/prototype, not a production language.

## Goals

FlowLang should make agent definitions:

- Human-readable.
- Deterministic to parse.
- Safe to validate before execution.
- Portable across Python, Rust, and Wasm hosts through FlowIR.
- Explicit about permissions, risk, identity, and economic behavior.

## Non-goals for v0

- No full parser generator.
- No arbitrary expressions.
- No user-defined functions.
- No imports/includes.
- No secrets.
- No hidden network or chain behavior.
- No runtime execution by itself.

## Syntax

FlowLang v0 is a strict line-oriented YAML/TOML-like subset.

Comments start with `#` outside quotes.

Top-level scalar directives:

```flowlang
agent FlowResearcher
identity did:flow:researcher-001
belief Verified memory is stronger than prompt-only context.
goal Produce grounded research briefs.
```

Blocks use `name:` headers and indented `key: value` fields:

```flowlang
memory:
  working_capacity: 7
  episodic: true
  semantic: true
  procedural: true
  economic: true
  adapters: [local]

policy economic-approval:
  permissions: [wallet.sign, marketplace.settle]
  risk: high
  requires_approval: true

skill settle-verified-work:
  description: Request local settlement after verification.
  permissions: [wallet.sign, marketplace.settle]
  risk: high

plan daily-research:
  goal: Research and summarize one verified topic.
  steps: [research-brief]
  risk: low

economy:
  settlement: local
  budget: 5
  currency: FLOW
  marketplace: local
  allow_slashing: true
```

## Supported declarations

### Agent

Required:

```flowlang
agent NAME
```

Validation rejects missing agent name.

### Identity

Optional for non-economic agents; required for economic settlement.

```flowlang
identity did:flow:agent-001
```

Validation rejects economic settlement without identity.

### Memory

```flowlang
memory:
  working_capacity: 7
  episodic: true
  semantic: true
  procedural: true
  economic: false
  adapters: [local]
```

Compiles to `MemorySpec`.

### Beliefs and goals

Beliefs and goals are repeated top-level lines:

```flowlang
belief Safety gates are mandatory for economic actions.
goal Complete verified marketplace tasks.
```

### Policies

```flowlang
policy safe-local:
  permissions: [respond, memory.read, audit.emit]
  risk: low
  requires_approval: false
```

Compiles to `PolicySpec`.

Allowed risk levels:

- `low`
- `medium`
- `high`
- `critical`

Validation rejects unknown risk levels.

### Skills

```flowlang
skill research-brief:
  description: Produce a grounded research brief.
  permissions: [memory.read, audit.emit]
  risk: low
```

Compiles to `SkillSpec`.

Unsafe skill permissions such as `wallet.sign`, `marketplace.settle`, `memory.write`, `tool.exec`, `shell.run`, and `contracts.call` require a policy that covers that exact permission.

### Plans

```flowlang
plan daily-research:
  goal: Research and summarize one verified topic.
  steps: [research-brief]
  risk: low
```

Validation rejects plans that reference missing skills.

### Economy

```flowlang
economy:
  settlement: local
  budget: 5
  currency: FLOW
  marketplace: local
  allow_slashing: true
```

Supported settlement modes in v0:

- `none`
- `local`
- `base-sepolia`
- `base`

`base-sepolia` and `base` are declaration modes only. They do not deploy or move funds.

## Compiler behavior

```text
FlowLang source -> AgentSpec -> validation -> JSON-serializable manifest
```

Python entrypoints:

- `flow_memory.flowlang.parse_flowlang(source)`
- `flow_memory.flowlang.validate_flowlang(source)`
- `flow_memory.flowlang.compile_flowlang(source)`
- `flow_memory.flowlang.compile_flowlang_file(path)`

## Example

See:

- `examples/flowlang_agent.flow`
- `examples/flowlang_compile_demo.py`

## Status

FlowLang v0 is a specification plus dependency-free parser/prototype. It is suitable for tests, examples, and design iteration. It is not yet a stable production language.
