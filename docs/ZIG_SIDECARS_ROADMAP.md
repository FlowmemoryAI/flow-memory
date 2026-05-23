# Zig Sidecars Roadmap

Zig is a candidate for memory-precise experimental sidecars and resource meters in Flow Memory.

## Why Zig

Zig gives explicit allocator control, simple cross-compilation, and low runtime overhead. Those traits are useful for narrow Flow Memory components that need precise memory/resource behavior without owning the full agent runtime.

## Candidate sidecars

- Resource meter for skill execution.
- Audit-log verifier utility.
- Deterministic memory-footprint probe.
- Small binary format checker for FlowIR manifests.
- Wasm component preflight scanner.

## Current status

- No Zig code is required.
- No Zig dependency is added.
- Rust remains the preferred future hardened runtime language.
- Zig is considered a sidecar language, not a core orchestration language.

## Experiment criteria

A Zig experiment is justified only when it:

1. Has a small, isolated responsibility.
2. Improves determinism, resource accounting, or deployability.
3. Has a Python/Rust-compatible test fixture.
4. Does not require global installation for default tests.
5. Does not bypass Flow Memory audit, policy, or sandbox boundaries.

## Avoid

Do not rewrite cognitive orchestration, economy logic, or policy semantics in Zig unless there is a measured need and a maintainer path.

## Decision

Classification: experiment only.

Zig should be used later for targeted sidecars if the runtime needs memory-precise measurement or small native tools.
