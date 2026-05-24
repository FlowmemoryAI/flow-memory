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
| POST | `/neural/live/sessions` | `neural:validate` | Create a local neural-live runtime session |
| GET | `/neural/live/sessions` | `neural:read` | List local neural-live runtime sessions |
| GET | `/neural/live/sessions/{session_id}` | `neural:read` | Inspect a local neural-live session |
| POST | `/neural/live/sessions/{session_id}/step` | `neural:validate` | Run one deterministic local neural step |
| POST | `/neural/live/sessions/{session_id}/learn` | `neural:train` | Run one deterministic local learning update |
| POST | `/neural/live/sessions/{session_id}/checkpoint` | `neural:validate` | Write checkpoint metadata only; no raw weights |
| POST | `/neural/live/sessions/{session_id}/stop` | `neural:validate` | Stop a local neural-live session |

Training endpoints remain local/public-alpha seams and must be protected with API-key/scope checks when auth is enabled.
Neural-live endpoints are deterministic and local by default. They do not make external model calls, download checkpoints, or claim GPU validation.
