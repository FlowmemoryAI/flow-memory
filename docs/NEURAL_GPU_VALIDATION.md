# Neural GPU validation

Smoke validation:

```bash
python scripts/gpu_env_check.py --json
python scripts/cloud_gpu_validate.py --smoke --json-out artifacts/cloud_gpu/local_smoke/validation.json
```

Full validation on a CUDA machine:

```bash
python scripts/gpu_env_check.py --require-cuda
python scripts/cloud_gpu_validate.py --full --json-out artifacts/cloud_gpu/gpu_full/validation.json
```

The script records pass/fail/skip results and clear next commands. It must pass on non-GPU machines by reporting missing CUDA rather than requiring it for the base repo.
