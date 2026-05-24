# Neural Evidence Release Gate

`python scripts/release_decision.py --target neural-gpu-smoke` evaluates the normal local evidence plus GPU evidence metadata. The target is for neural smoke confidence only; it is not production ML certification.

Required evidence path: `release_evidence/gpu_runs/<run_id>/summary.json` and `hashes.json`. The launch run id is `flow-memory-cloud-gpu-run-001`, matching the RunPod artifact name.

Missing local artifacts are still importable as explicit skipped records so developers can run the scripts offline, but the `neural-gpu-smoke` release decision now requires at least one non-skipped verified GPU run. A skipped record is not launch evidence.
