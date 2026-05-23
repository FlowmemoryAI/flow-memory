# RunPod GPU quickstart

## 1. Create a pod

Recommended first GPU: RTX 4090 or RTX 5090. Heavier option: A100 80 GB.

Template: PyTorch / CUDA / Jupyter / SSH.

Disk: 80-120 GB minimum. Use a persistent volume if you want checkpoints and artifacts to survive pod deletion. Container disk can be temporary; volumes may keep billing after compute stops.

Budget controls:
- Start with a one-hour smoke run.
- Stop or delete idle pods.
- Back up artifacts before deleting storage.
- Never store private keys or cloud credentials in the repo.

## 2. SSH and verify GPU

```bash
nvidia-smi
python --version
git --version
```

`nvidia-smi` should show the rented GPU.

## 3. Clone Flow Memory

```bash
git clone https://github.com/FlowmemoryAI/flow-memory.git
cd flow-memory
git rev-parse --short HEAD
```

You should see `948f70d` or a later commit.

## 4. Create the environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev,ml]"
```

Check Torch/CUDA:

```bash
python scripts/gpu_env_check.py --require-cuda
```

## 5. Run validation

```bash
python -m pytest -q
python -m pytest -q tests/test_tiny_dual_stream_encoder.py tests/test_tiny_jepa_world_model.py tests/test_cli_neural_flag.py
python examples/neural_perception_demo.py
python examples/neural_world_model_demo.py
python examples/neural_plan_scoring_demo.py
python examples/neural_agent_demo.py
python -m flow_memory --neural tiny_torch --json "Explore and report"
python scripts/cloud_gpu_validate.py --smoke --json-out artifacts/cloud_gpu/runpod_smoke/validation.json
```

## 6. Run benchmarks

```bash
python benchmarks/neural_appearance_free_motion_benchmark.py
python benchmarks/neural_world_model_prediction_benchmark.py
python benchmarks/neural_plan_scoring_benchmark.py
python benchmarks/neural_memory_retrieval_benchmark.py
python benchmarks/neural_agent_policy_benchmark.py
```

## 7. Run training smoke scripts

```bash
python -m flow_memory.neural.training.train_tiny_dual_stream
python -m flow_memory.neural.training.train_world_model
python -m flow_memory.neural.training.train_agent_policy
python -m flow_memory.neural.training.evaluate_neural_stack
python scripts/train_neural_smoke.py --out artifacts/neural/smoke
python scripts/train_neural_gpu.py --steps 10 --out artifacts/neural/gpu_smoke
```

## 8. Package artifacts before stopping the pod

```bash
python scripts/package_gpu_artifacts.py --input artifacts/cloud_gpu/runpod_smoke --out artifacts/cloud_gpu/runpod_smoke.tar.gz
python scripts/summarize_gpu_artifacts.py artifacts/cloud_gpu/runpod_smoke
```

Download the `.tar.gz` file before deleting the pod or non-persistent disk.
