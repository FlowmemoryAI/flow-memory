# Neural evidence release gate

`python scripts/release_decision.py --target neural-gpu-smoke` evaluates whether local release gates pass and at least one imported neural GPU run proves the smoke lane.

Required neural evidence:

- `neural_gpu_runs` in the release evidence bundle.
- `gpu_artifact_hashes` from `hashes.json`.
- `gpu_validation_summary` from `summary.json` / `summary.md`.
- `neural_cli_status` parsed from validation metadata.
- `neural_benchmark_status` parsed from validation metadata.

A passing neural GPU smoke record must include:

- GPU name.
- CUDA availability confirmed as true.
- Torch version.
- CLI neural status ok.
- Neural benchmark status ok.

Missing local artifacts do not fail base tests. They do block the `neural-gpu-smoke` release target with `neural_gpu_ingestion_skipped` until a real imported artifact is present.

Export and verify bundle evidence:

```bash
python scripts/export_release_evidence.py
python scripts/verify_release_evidence.py
python scripts/release_decision.py --target neural-gpu-smoke
```
