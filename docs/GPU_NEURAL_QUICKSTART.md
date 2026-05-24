# GPU Neural Quickstart

Optional ML path:

```bash
pip install -e ".[dev,ml]"
python scripts/gpu_env_check.py --json
python -m flow_memory --neural tiny_torch --json "Explore and report"
python benchmarks/neural_plan_scoring_benchmark.py
python scripts/train_neural_smoke.py --out artifacts/neural/smoke
```

Cloud GPU evidence can be imported only if the real artifact is present:

```bash
mkdir -p artifacts/incoming
# copy flow-memory-cloud-gpu-run-001.tar.gz into artifacts/incoming/
python scripts/import_gpu_run_artifact.py artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz
python scripts/verify_gpu_run_artifact.py flow-memory-cloud-gpu-run-001
python scripts/summarize_gpu_run.py flow-memory-cloud-gpu-run-001
python scripts/release_decision.py --target neural-gpu-smoke
```

Do not commit checkpoint weights or large generated artifacts. V-JEPA 2 and VideoMAE remain adapter seams unless local checkpoints are supplied and evaluated.
