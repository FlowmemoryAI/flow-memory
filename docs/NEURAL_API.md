# Neural API

The dependency-free local API exposes neural metadata and GPU evidence without raw model downloads.

Endpoints:

| Method | Path | Scope | Purpose |
| --- | --- | --- | --- |
| GET | `/neural/status` | `neural:read` | Torch/CUDA/backend status |
| GET | `/neural/backends` | `neural:read` | Available and seam backends |
| GET | `/neural/gpu-runs` | `neural:evidence` | Imported GPU evidence records |
| GET | `/neural/gpu-runs/{run_id}` | `neural:evidence` | One GPU evidence summary |
| GET | `/neural/benchmarks` | `neural:read` | Local benchmark artifact metadata |
| GET | `/neural/checkpoints` | `neural:read` | Checkpoint metadata only, never raw weights |
| POST | `/neural/validate-smoke` | `neural:validate` | Local smoke validation command metadata |
| POST | `/neural/train-smoke` | `neural:train` | Local-only tiny training smoke lane |

Training endpoints remain local/public-alpha seams and must be protected with API-key/scope checks when auth is enabled.
