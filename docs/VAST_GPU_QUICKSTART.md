# Vast.ai GPU quickstart

Vast.ai can be cheaper but instance quality varies. Prefer verified hosts, recent CUDA images, SSH access, enough disk, and no suspicious templates.

Beginner checklist:

1. Choose a PyTorch/CUDA image.
2. Prefer RTX 4090/5090 for first smoke runs.
3. Allocate enough disk for repo, venv, and artifacts.
4. Run `nvidia-smi` immediately after SSH.
5. Do not store API keys, private keys, or recovery words.

Commands:

```bash
nvidia-smi
git clone https://github.com/FlowmemoryAI/flow-memory.git
cd flow-memory
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev,ml]"
python scripts/gpu_env_check.py --require-cuda
python scripts/cloud_gpu_validate.py --smoke --json-out artifacts/cloud_gpu/vast_smoke/validation.json
python scripts/package_gpu_artifacts.py --input artifacts/cloud_gpu/vast_smoke --out artifacts/cloud_gpu/vast_smoke.tar.gz
```
