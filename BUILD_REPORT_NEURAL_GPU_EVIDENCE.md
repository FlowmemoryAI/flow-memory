# Neural GPU evidence build report

Branch: `work/neural-gpu-evidence`

## Scope

Implemented neural GPU evidence ingestion, release-evidence integration, and dependency-free neural API endpoints.

## Artifact status

Expected artifact: `artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz`

Local ingestion status: skipped because the artifact is not present in this checkout. A skipped evidence record was generated at `release_evidence/gpu_runs/flow-memory-cloud-gpu-run-001/`.

## Validation results

- `python -m pytest -q` — 347 passed, 17 skipped.
- `bash scripts/verify.sh` — passed, including release gate secret scan.
- `python scripts/gpu_env_check.py --json` — ok; local machine has no torch/CUDA/nvidia-smi.
- `python scripts/cloud_gpu_validate.py --smoke --json-out artifacts/cloud_gpu/local_smoke/validation.json` — ok.
- `python scripts/train_neural_smoke.py --out artifacts/neural/smoke` — ok, skipped training because torch is not installed locally.
- `python scripts/export_release_evidence.py` — ok.
- `python scripts/verify_release_evidence.py` — ok.
- `python scripts/release_decision.py --target local` — ok.
- `python scripts/release_decision.py --target neural-gpu-smoke` — blocked with `neural_gpu_ingestion_skipped` because the expected GPU artifact is absent locally.
- `python scripts/run_local_api_server.py --help` — ok.
- `docker compose config` — ok.
- `forge build` — ok.
- `forge test` — 16 passed.
- `cargo test` — 2 passed.
- `git diff --check` — ok.
- `python scripts/release_gate.py` — ok, `secret_scan` match_count 0.
