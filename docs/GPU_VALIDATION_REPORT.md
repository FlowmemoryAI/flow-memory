# GPU validation report

## Operator-provided RunPod validation

The neural GPU evidence lane was designed around the manually validated RunPod RTX 4090 run reported for this branch:

- GPU: NVIDIA GeForce RTX 4090
- Torch: 2.12.0+cu130
- CUDA available: True
- Pytest observed: 339 passed, 3 skipped
- CLI neural backend: `tiny_torch` available
- Neural benchmarks: ok
- Expected artifact: `artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz`

## Local ingestion status

If the artifact is present, import it with:

```bash
python scripts/import_gpu_run_artifact.py --artifact artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz
python scripts/verify_gpu_run_artifact.py flow-memory-cloud-gpu-run-001
python scripts/summarize_gpu_run.py flow-memory-cloud-gpu-run-001
```

If the artifact is absent, the importer writes a skipped evidence record under `release_evidence/gpu_runs/flow-memory-cloud-gpu-run-001/` and exits successfully. Base tests must continue to pass without the raw artifact.

## Evidence generated

Each imported run produces:

- `summary.json` — parsed GPU, torch, CUDA, git, CLI neural, benchmark, pytest, and checkpoint-count metadata.
- `summary.md` — human-readable summary.
- `hashes.json` — archive hash plus hashes for every archive member and extracted metadata file.
- `metadata/` — extracted small UTF-8 text/JSON files only.

Weights and checkpoints are hashed as archive members but are not extracted into release evidence.
