# RL Arena Quickstart

Flow Arena provides small local environments where agents can learn advisory policies before touching real tools or money.

Run examples:

```bash
python examples/rl_safety_gate_demo.py
python examples/rl_economy_market_demo.py
python examples/launch_rl_trained_agent_demo.py
```

Run benchmarks:

```bash
python benchmarks/rl_training_smoke_benchmark.py
python benchmarks/rl_policy_comparison_benchmark.py
```

Policy outputs are advisory. RL suggestions cannot execute actions directly and cannot bypass PolicyEngine, ApprovalGate, autonomy mode, or economy risk controls.
