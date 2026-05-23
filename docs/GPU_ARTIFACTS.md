# GPU artifacts

Generated artifacts belong under `artifacts/`, which is ignored by git.

Recommended layout:

```
artifacts/
  cloud_gpu/<run_id>/
    validation.json
    gpu_info.json
    metrics.json
    training_log.jsonl
    model_card.md
    checkpoint_manifest.json
  neural/checkpoints/
```

Package a run:

```bash
python scripts/package_gpu_artifacts.py --input artifacts/cloud_gpu/runpod_smoke --out artifacts/cloud_gpu/runpod_smoke.tar.gz
python scripts/summarize_gpu_artifacts.py artifacts/cloud_gpu/runpod_smoke
```

The package script records hashes for checkpoint files but does not make generated weights suitable for git.
