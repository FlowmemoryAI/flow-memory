# Flow Arena Native Backend Roadmap

Flow Arena is currently a dependency-light Python RL layer. A native backend is future work for throughput, not a prerequisite for public alpha.

## Maturity

| Backend | Status | Claim control |
| --- | --- | --- |
| Python FlowEnv | functional prototype | local deterministic training/evaluation only |
| Optional Torch trainer | smoke prototype | advisory policy training, skips without torch/CUDA |
| PufferLib adapter | adapter seam | no Puffer dependency or performance claim |
| Native C envs | planned | no implementation yet |
| CUDA env backend | planned | no implementation yet |
| Browser/WASM demo | static prototype path | no neural inference claim |

## Build order

1. Freeze observation/action/reward schemas for each Flow Arena environment.
2. Add parity tests comparing Python env traces to serialized golden traces.
3. Implement native C candidates for `SafetyGateEnv` and `EconomyMarketEnv` first.
4. Add Puffer/Ocean wrappers around native envs only after parity passes.
5. Add CUDA batching only after CPU native envs are deterministic and safe.
6. Export browser policy demos from tabular/heuristic policies before any neural browser work.

## Safety boundary

Native/Puffer/CUDA policies must remain advisory. They may suggest actions and estimate values, but PolicyEngine, ApprovalGate, autonomy mode, risk budgets, and economy settlement checks remain authoritative.

## Public-alpha limitation

Public alpha does not include PufferLib-level throughput, CUDA RL environments, native C envs, production fraud detection, or real-funds autonomous execution.
