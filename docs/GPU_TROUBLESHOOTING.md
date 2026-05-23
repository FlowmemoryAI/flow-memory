# GPU troubleshooting

- Torch not installed: run `pip install -e ".[dev,ml]"` inside the activated venv.
- CUDA unavailable: check `nvidia-smi`, provider GPU selection, CUDA PyTorch build, and driver compatibility.
- `nvidia-smi` not found: choose a GPU template with NVIDIA drivers or use the provider's CUDA image.
- Wrong Python env: confirm `which python` and `python -m pip --version`.
- Out of memory: reduce `--batch-size`, reduce `--steps`, or choose a larger GPU.
- Disk full: use larger disk/volume, clean caches, package and move artifacts.
- Pod stopped: restart and verify whether disk was persistent.
- Checkpoint too large: keep weights under `artifacts/` and package only needed files.
- Pip install issues: upgrade pip/setuptools/wheel and verify network access.
