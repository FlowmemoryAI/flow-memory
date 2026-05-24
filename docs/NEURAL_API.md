# Neural API

The dependency-free local HTTP server and in-process router expose neural metadata and smoke-operation endpoints without FastAPI.

## Endpoints

- `GET /neural/status` — local torch/CUDA status plus neural GPU evidence gate status.
- `GET /neural/backends` — configured backend names and local availability.
- `GET /neural/gpu-runs` — imported GPU evidence summaries.
- `GET /neural/gpu-runs/{run_id}` — one imported GPU evidence summary.
- `GET /neural/benchmarks` — benchmark evidence metadata from imported GPU runs.
- `GET /neural/checkpoints` — checkpoint metadata only: name, relative path, size, hash. It never returns raw weights.
- `POST /neural/validate-smoke` — local neural smoke validation metadata.
- `POST /neural/train-smoke` — local tiny neural training smoke run under `artifacts/neural/...`.

## Scopes

When `--require-scopes` is enabled on `scripts/run_local_api_server.py`, neural routes require dedicated scopes:

- `neural:read` for `/neural/status`, `/neural/backends`, and `/neural/checkpoints`.
- `neural:evidence` for `/neural/gpu-runs`, `/neural/gpu-runs/{run_id}`, and `/neural/benchmarks`.
- `neural:validate` for `/neural/validate-smoke`.
- `neural:train` for `/neural/train-smoke`.

`neural:train` is only honored on loopback server bindings (`127.0.0.1`, `localhost`, or `::1`).

## Examples

```bash
python scripts/run_local_api_server.py --api-key dev --require-scopes
```

```http
GET /neural/status
X-Flow-Memory-API-Key: dev
X-Flow-Memory-Scopes: neural:read
```

```http
POST /neural/train-smoke
X-Flow-Memory-API-Key: dev
X-Flow-Memory-Scopes: neural:train
Content-Type: application/json

{"steps": 1, "out": "artifacts/neural/api_train_smoke"}
```

The training response includes metrics and checkpoint hashes only. Generated weights remain under ignored `artifacts/` paths.
