# Lambda Cloud GPU quickstart

Lambda Cloud is a good second path when you want a more standard GPU VM. Pick an instance with recent NVIDIA drivers and enough disk for the repo, virtualenv, artifacts, and checkpoints.

Recommended flow:

```bash
nvidia-smi
git clone https://github.com/FlowmemoryAI/flow-memory.git
cd flow-memory
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev,ml]"
python scripts/gpu_env_check.py --require-cuda
python scripts/cloud_gpu_validate.py --smoke --json-out artifacts/cloud_gpu/lambda_smoke/validation.json
python scripts/train_neural_smoke.py --out artifacts/neural/smoke
python scripts/package_gpu_artifacts.py --input artifacts/cloud_gpu/lambda_smoke --out artifacts/cloud_gpu/lambda_smoke.tar.gz
```

Do not leave idle GPU instances running. Copy artifact tarballs off the VM before deleting ephemeral disks.
