# Public Alpha Launch Checklist

Flow Memory public alpha should launch only after these local/testnet-oriented gates are satisfied.

## Required before tagging

- [ ] `python -m pytest -q` passes.
- [ ] `bash scripts/verify.sh` passes.
- [ ] `python scripts/release_decision.py --target local` passes.
- [ ] Real RunPod artifact exists at `artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz`.
- [ ] `python scripts/import_gpu_run_artifact.py artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz` imports a non-skipped GPU run.
- [ ] `python scripts/release_decision.py --target neural-gpu-smoke` passes.
- [ ] RL benchmarks have been regenerated under `artifacts/rl/`.
- [ ] `python scripts/export_release_evidence.py` and `python scripts/verify_release_evidence.py` pass.
- [ ] `python scripts/release_decision.py --target public-alpha-neural` passes.
- [ ] No secrets, model weights, checkpoint binaries, or private keys are committed.

## Launch framing

Flow Memory Public Alpha: The human compute network for neural AI agents.

Claims allowed:

- public alpha
- local/testnet/dry-run oriented
- neural advisory layer
- RL Arena prototype
- safety gates authoritative

Claims not allowed:

- production certified
- mainnet ready
- audited contracts
- hardened sandbox
- production ML quality
