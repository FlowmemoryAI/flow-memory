# RL Arena API

The dependency-free local API exposes Flow Arena metadata and short local-only evaluation/training paths.

| Method | Path | Scope | Purpose |
| --- | --- | --- | --- |
| GET | `/rl/envs` | `rl:read` | List registered local Flow Arena environments |
| GET | `/rl/benchmarks` | `rl:read` | List RL benchmark artifact metadata |
| POST | `/rl/evaluate` | `rl:evaluate` | Evaluate random/heuristic/tabular policies locally |
| POST | `/rl/train-smoke` | `rl:train` | Run a short tabular Q smoke trainer locally |

Examples:

```bash
python scripts/run_local_api_server.py --api-key dev-local-only --require-scopes
```

Internal router payloads:

```json
{"env_id": "safety_gate", "policy": "heuristic", "episodes": 5}
```

Training is intentionally local and bounded. RL suggestions remain advisory and cannot bypass PolicyEngine, ApprovalGate, autonomy mode, or economic risk controls.
