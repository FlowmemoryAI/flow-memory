# Cloud GPU setup for Flow Memory Neural Agent Layer

This runbook is for a beginner operator who wants to validate the optional neural lane on rented GPU compute without changing the base install. The normal Flow Memory test suite must keep passing without GPU, torch, cloud credentials, or network services.

Supported paths, in order:

1. RunPod first: easiest for a short PyTorch/CUDA pod.
2. Lambda Cloud second: simpler dedicated GPU VM path.
3. Vast.ai third: often cheaper, more marketplace variability.
4. Local Linux GPU: optional if CUDA/PyTorch already work.
5. PufferLib: future RL lane, not required now.

High-level flow:

```bash
git clone https://github.com/FlowmemoryAI/flow-memory.git
cd flow-memory
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev,ml]"
python scripts/gpu_env_check.py --require-torch
python scripts/cloud_gpu_validate.py --smoke --json-out artifacts/cloud_gpu/runpod_smoke/validation.json
python scripts/train_neural_smoke.py --out artifacts/neural/smoke
python scripts/package_gpu_artifacts.py --input artifacts/cloud_gpu/runpod_smoke --out artifacts/cloud_gpu/runpod_smoke.tar.gz
```

Never commit API keys, private keys, recovery words, checkpoints, or generated model weights.
