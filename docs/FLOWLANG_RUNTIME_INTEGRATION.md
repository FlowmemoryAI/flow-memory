# FlowLang Runtime Integration

## Purpose

FlowLang is the human-readable agent declaration language for Flow Memory. Its runtime integration path is: FlowLang source, FlowIR dataclasses, JSON manifest, optional signed envelope, then runtime admission by policy, skill, memory, and economy layers.

## Implemented behavior

Status: implemented parser/prototype and adapter seam.

- `flow_memory.flowlang` exposes `parse_flowlang`, `validate_flowlang`, `compile_flowlang`, and file-based variants.
- FlowLang v0 compiles into FlowIR `AgentSpec` structures and JSON-serializable manifests.
- FlowIR includes agent, memory, policy, skill, plan, and economy dataclasses.
- `flow_memory.ir.manifest` provides versioned manifest envelopes, deterministic canonical JSON, SHA-256 digests, and local development HMAC signing helpers.
- WIT files define intended component boundaries for future Wasm hosts, but the Python runtime remains the active local execution path.

## Limitations

- FlowLang is v0 and line-oriented; it is not a stable production language.
- Compiled manifests are not yet the enforced admission source for every runtime subsystem.
- HMAC signing is a deterministic development integrity helper, not production deployment signing.
- No Rust/Wasm host currently executes FlowIR manifests.
- Datalog policy rules are starter rules and are not yet wired into runtime enforcement.

## Next steps

- Treat signed FlowIR envelopes as the mandatory runtime admission format.
- Add schema migration/version negotiation for FlowIR manifests.
- Wire manifest permissions into skill execution, policy approval, memory access, and economy bids.
- Implement an external validator/host boundary for untrusted FlowLang artifacts.
- Add conformance fixtures for parser, compiler, manifest, and runtime admission parity.
