# RL Benchmarks

Local benchmarks export JSON under `artifacts/rl/`:

- `benchmarks/rl_env_throughput_benchmark.py`
- `benchmarks/rl_training_smoke_benchmark.py`
- `benchmarks/rl_safety_gate_benchmark.py`
- `benchmarks/rl_economy_market_benchmark.py`

Metrics include throughput, mean reward, success rate, safety violation rate, dispute/slashing rate where applicable, and prototype reward improvement.


## Policy comparison

`benchmarks/rl_policy_comparison_benchmark.py` compares random, heuristic, and tabular Q policies on a deterministic Flow Arena environment and writes `artifacts/rl/rl_policy_comparison_benchmark.json`.

`src/flow_memory/rl/torch_trainer.py` adds an optional torch actor-critic smoke trainer behind the `ml` extra. If torch or CUDA is missing, the trainer reports a structured skip; it does not affect the base test suite and it is not a production PPO/A2C implementation.
