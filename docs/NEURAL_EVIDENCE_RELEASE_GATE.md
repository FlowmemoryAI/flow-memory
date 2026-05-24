# Neural Evidence Release Gate

`python scripts/release_decision.py --target neural-gpu-smoke` evaluates the normal local evidence plus GPU evidence metadata. The target is for neural smoke confidence only; it is not production ML certification.

Required evidence path: `release_evidence/gpu_runs/<run_id>/summary.json` and `hashes.json`. Missing local artifact imports are explicit skipped records so offline developer validation remains possible.
