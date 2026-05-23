# Flow Memory Language Strategy

## Thesis

Flow Memory should not become another Python-only or TypeScript-only agent framework. It should become a polyglot autonomous agent OS where each language is used for the part of the system where it has a real operational advantage.

The target architecture is:

| Layer | Primary language/tool | Role |
| --- | --- | --- |
| Cognitive orchestration | Python | Fast iteration, ML integration, docs/examples, local agent loop. |
| Hardened runtime | Rust | Audit log, sandbox host, Wasm host, policy enforcement, high-assurance runtime services. |
| Memory-precise sidecars | Zig | Experimental resource meters, deterministic sidecars, allocator-aware memory probes. |
| Neural kernels | Mojo | Optional AI-native kernels when the ecosystem is mature enough. |
| Language-neutral skills | WebAssembly Component Model + WIT | Sandboxed, typed skill ABI across Rust, Python, TypeScript, Go, Zig, and future languages. |
| Policy/reasoning | Datalog/Souffle/Ascent | Memory, reputation, task eligibility, slashing, and policy inference. |
| Swarm supervision | Gleam/Elixir | Experimental actor supervision and fault-tolerant multi-agent coordination. |
| Settlement | Solidity | Base-chain agent registry, escrow, reputation, attestations, disputes, slashing. |
| Dashboard/SDK/tooling | TypeScript | Browser dashboard, SDKs, CLI companions, generated clients. |
| Cognitive DSL | FlowLang | Human-readable agent declarations that compile to FlowIR. |

## What to use now

### Python

Use Python now for Flow Memory's cognitive kernel, FlowIR/FlowLang prototype, perception seams, memory orchestration, local economy emulator, examples, and tests. Python remains the fastest path for research-grade agent runtime iteration and ML integration.

Rules:

- Keep Python runtime deterministic by default.
- Keep no-key/no-network local paths working.
- Use dataclasses and plain mappings for interfaces that may later be hosted by Rust or Wasm.
- Avoid hiding unsafe behavior behind dynamic magic.

### Solidity

Use Solidity now for the Base-chain settlement prototype, but do not claim deployment readiness. Contracts should remain small, auditable, and tested locally with Foundry.

### WIT and WebAssembly Component Model

Use WIT now as interface files, not as a production host. WIT defines contracts between components and is suitable for the Flow Memory skill ABI because it does not prescribe implementation language.

### Datalog-style rules

Use readable Datalog/Souffle-style rules now as policy specifications and test fixtures. Do not require Souffle in the default install until the Rust/runtime policy boundary exists.

### FlowLang v0

Use FlowLang now as a v0 specification and parser prototype that compiles to FlowIR. Do not market it as a production language.

## What to use later

### Rust

Rust should become the hardened runtime language for:

- Wasm host execution.
- Audit log hashing and verification.
- Capability enforcement.
- Policy engine integration.
- Sandboxed process/resource management.
- Signed manifest verification.

Rust is not required to rewrite the Python cognitive kernel. It should harden boundaries where memory safety, capability safety, and predictable execution matter.

### TypeScript

TypeScript should power:

- Web dashboard.
- Generated API clients.
- Skill developer tooling.
- FlowLang editor support.
- Browser-based local demos.

### Ascent

Ascent is a Rust-native Datalog-style option to evaluate when Rust policy hosting starts. It may be a better operational fit than requiring Souffle binaries in the default developer path.

## Experiment only

### Zig

Zig is valuable for allocator-aware sidecars, deterministic resource meters, and small native probes. It should not become the core agent language until there is a proven need.

### Mojo

Mojo is promising for AI-native kernels, but Flow Memory should treat it as optional and experimental until packaging, CI, and contributor availability are proven.

### Gleam and Elixir

Both are good candidates for actor supervision experiments. Elixir/OTP is mature for supervision; Gleam is safer and statically typed. Neither should be required by the core runtime yet.

### Pony, MoonBit, Koka

These are interesting for capability safety, Wasm, or effect systems, but they are not core dependencies. Use them only for research prototypes.

### AgentSpeak/Jason/GOAL

These are useful BDI-agent references. FlowLang should learn from them, but Flow Memory should not adopt them directly as core syntax.

### BAML, SGLang, DSPy

These are prompt/programming frameworks worth watching. They may influence model-call and evaluation layers, but they should not define the OS boundary.

### Hoon/Nock/Urbit

Use as inspiration for deterministic agents, identity, and event logs only. Avoid adopting Urbit-specific runtime assumptions.

## Avoid for core

Avoid making the core depend on languages or tools that:

- Break the no-key/no-network local path.
- Require global installs for basic tests.
- Have unclear Windows support.
- Add runtime complexity without a safety, performance, or developer-experience win.

## Flow Memory language boundary

The language boundary should look like this:

```text
FlowLang source
  -> FlowIR dataclasses
  -> JSON manifest
  -> Python local runtime today
  -> Rust/Wasm host later
  -> Datalog policy/reputation/slashing inference
  -> Solidity settlement where explicitly enabled
```

This lets Flow Memory differentiate without rewriting the existing project.

## Immediate implementation status

Implemented in this layer:

- FlowIR dataclasses in `src/flow_memory/ir/`.
- FlowLang v0 parser/validator in `src/flow_memory/flowlang/`.
- WIT ABI files in `wit/`.
- Datalog starter rules in `rules/`.
- FlowLang example and compile demo in `examples/`.

Status: v0 specification plus parser/prototype, not production-ready.
