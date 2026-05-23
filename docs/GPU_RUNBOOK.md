# GPU runbook

1. Launch a RunPod/Lambda/Vast GPU instance.
2. Verify with `nvidia-smi`.
3. Clone Flow Memory and create `.venv`.
4. Install `pip install -e ".[dev,ml]"`.
5. Run `python scripts/gpu_env_check.py --require-cuda`.
6. Run `python scripts/cloud_gpu_validate.py --smoke --json-out artifacts/cloud_gpu/<run_id>/validation.json`.
7. Run `python scripts/train_neural_smoke.py --out artifacts/neural/smoke`.
8. If CUDA is available, run `python scripts/train_neural_gpu.py --steps 10 --out artifacts/neural/gpu_smoke`.
9. Package artifacts with `python scripts/package_gpu_artifacts.py --input artifacts/cloud_gpu/<run_id> --out artifacts/cloud_gpu/<run_id>.tar.gz`.
10. Download artifacts and stop/delete the pod.
