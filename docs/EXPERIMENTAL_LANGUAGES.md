# Experimental Languages and Frameworks

This document classifies language and framework candidates for Flow Memory. The goal is to differentiate Flow Memory without adding fashionable dependencies that weaken local reliability.

| Candidate | Classification | Reason |
| --- | --- | --- |
| Python | Use now | Best current language for cognitive orchestration, ML integration, examples, tests, and fast iteration. |
| Rust | Use later | Best fit for hardened runtime, Wasm host, audit verification, sandbox/capability enforcement. |
| TypeScript | Use later | Best fit for dashboard, SDK, generated clients, browser tooling, and FlowLang editor support. |
| Solidity | Use now | Required for Base-chain settlement prototypes; must remain unaudited/testnet-only until reviewed. |
| WebAssembly Component Model/WIT | Use now | Define ABI now; implement host later. Good language-neutral skill boundary. |
| Datalog/Souffle/Ascent | Use now for specs, use later for runtime | Starter rules are useful now; runtime integration should wait for host/fact pipeline. |
| Zig | Experiment only | Good for resource meters and sidecars, not core orchestration. |
| Mojo | Experiment only | Promising for AI-native kernels, but not stable enough as a required dependency. |
| Gleam | Experiment only | Interesting typed actor language for swarm supervision experiments. |
| Elixir | Use later for experiments | OTP supervision is strong, but a required BEAM runtime is too heavy for core today. |
| Pony | Experiment only | Capability-safe actor model is interesting, ecosystem cost is high. |
| MoonBit | Experiment only | Wasm-oriented language worth watching, not core today. |
| Koka | Experiment only | Effect typing is relevant to safe agents, but not operationally mature enough for core. |
| AgentSpeak/Jason/GOAL | Experiment only | Valuable BDI references; FlowLang should learn from them without adopting full syntax. |
| BAML | Experiment only | Useful prompt/interface ideas; not a core OS language. |
| SGLang | Experiment only | Useful for model-serving/programming patterns; not the agent OS boundary. |
| DSPy | Experiment only | Useful optimization/evaluation reference; avoid making it core. |
| Hoon/Nock/Urbit | Inspiration only | Deterministic identity/event-log ideas are relevant, but runtime assumptions do not fit Flow Memory core. |

## Use now

Use now means the project can carry files, tests, docs, or prototype code without weakening the default developer path.

- Python
- Solidity
- WIT files
- Datalog-style starter rules
- FlowLang v0 and FlowIR

## Use later

Use later means the language should be introduced only at a hardened boundary with clear tests and build isolation.

- Rust
- TypeScript
- Ascent
- Elixir/Gleam supervision experiments

## Experiment only

Experiment only means no core dependency and no default validation requirement.

- Zig
- Mojo
- Pony
- MoonBit
- Koka
- AgentSpeak/Jason/GOAL
- BAML
- SGLang
- DSPy

## Avoid for core

Avoid for core means do not let the candidate define the repository's required install path or agent semantics.

- Hoon/Nock/Urbit
- Any experimental language without Windows-friendly install and CI support
- Any prompt framework that hides policy, memory, or economy effects

## Principle

Flow Memory should be polyglot at the boundary, boring at the core, and strict at the safety layer.
