# RL Setup for Beginners

No GPU is required for Flow Arena. From a fresh checkout:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
python -m pytest -q tests/test_rl_optional_imports.py tests/test_flow_env_api.py
python examples/rl_safety_gate_demo.py
python benchmarks/rl_training_smoke_benchmark.py
```

Generated RL artifacts are written under `artifacts/rl/` and are ignored by git.
