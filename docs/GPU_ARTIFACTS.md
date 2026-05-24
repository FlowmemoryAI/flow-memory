# GPU artifacts

Generated GPU and neural artifacts belong under `artifacts/`, which is ignored by git.

Recommended layout:

```
artifacts/
  incoming/
    flow-memory-cloud-gpu-run-001.tar.gz
  cloud_gpu/<run_id>/
    validation.json
    gpu_info.json
    metrics.json
    training_log.jsonl
    model_card.md
    checkpoint_manifest.json
  neural/checkpoints/
```

Package a run on the GPU host:

```bash
python scripts/package_gpu_artifacts.py --input artifacts/cloud_gpu/runpod_smoke --out artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz
python scripts/summarize_gpu_artifacts.py artifacts/cloud_gpu/runpod_smoke
```

Import safe release evidence locally:

```bash
python scripts/import_gpu_run_artifact.py --artifact artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz
python scripts/verify_gpu_run_artifact.py flow-memory-cloud-gpu-run-001
python scripts/summarize_gpu_run.py flow-memory-cloud-gpu-run-001
python scripts/compare_gpu_runs.py release_evidence/gpu_runs/<left> release_evidence/gpu_runs/<right>
```

The import layer hashes the raw archive and every archive member, but it extracts only small UTF-8 text/JSON metadata. Checkpoints and weights (`.pt`, `.pth`, `.ckpt`, `.safetensors`, `.onnx`, `.bin`) are never committed or served as raw bytes.
