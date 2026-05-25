# API Agent Launch Endpoints

The dependency-free local API server now exposes public-alpha launch endpoints:

| Method | Path | Scope when enabled | Purpose |
| --- | --- | --- | --- |
| POST | `/agents/launch` | `agents:launch` | Launch a local AgentProfile/AgentRunner cycle. |
| POST | `/agents/launch-flowlang` | `agents:launch` | Compile and run FlowLang source. |
| POST | `/agents/launch-neural` | `agents:launch` | Launch an agent with neural advisory metadata. |
| POST | `/launch/agent` | `agents:launch` | Run the Live Agent Launchpad from a built-in template. |
| POST | `/launch/agent/from-flow` | `agents:launch` | Run the Live Agent Launchpad from FlowLang source. |
| POST | `/network/run-scenario` | `network:run` | Run a local network scenario. |

Example with local API-key/scopes:

```bash
python scripts/run_local_api_server.py --api-key dev-local-only --require-scopes
```

Send `X-Flow-Memory-API-Key: dev-local-only` and `X-Flow-Memory-Scopes: agents:launch` for agent launch calls.

Launchpad request example:

```json
POST /launch/agent
{
  "template": "live-research",
  "ticks": 5,
  "neural": {
    "enabled": true,
    "backend": "tiny_torch",
    "live_mode": true,
    "learning_enabled": true
  },
  "emit_visual": true
}
```

The response includes the launch summary, replay events, visual state, memory record metadata, and local-only safety invariants.

These endpoints are local/public-alpha seams, not production internet auth or hosted orchestration.

## Live Agent Operations API

After launching an agent, inspect local run records with:

```http
GET /launch/runs
GET /launch/runs/{run_id}
POST /launch/runs/{run_id}/replay
POST /launch/runs/{run_id}/export
POST /launch/runs/{run_id}/stop
```

Scopes when enabled:

- `launch:read` for list/show/replay
- `launch:export` for bundle export
- `launch:run` for stop/no-op operations

These endpoints read and write local JSON metadata only. They do not call external providers, move funds, or manage hidden background processes.

## Live Agent Supervisor API

```http
POST /launch/supervisor/start
GET /launch/supervisor/status
GET /launch/supervisor/runs/{run_id}
GET /launch/supervisor/runs/{run_id}/heartbeat
POST /launch/supervisor/runs/{run_id}/pause
POST /launch/supervisor/runs/{run_id}/resume
POST /launch/supervisor/runs/{run_id}/stop
```

Example request:

```json
{
  "template": "live-research",
  "ticks": 5,
  "tick_interval_ms": 10,
  "neural": {"backend": "tiny_torch"},
  "emit_visual": true
}
```

Supervisor endpoints are local-only and bounded. Scope requirements: `launch:read` for status/show/heartbeat, `launch:run` for start/resume, and `launch:control` for pause/stop.

## Mission Control run console and demo bundle API

```http
GET /launch/console/runs
GET /launch/console/runs/{run_id}
GET /launch/console/fixtures
POST /launch/bundles/public-alpha
```

Example bundle request:

```json
{
  "out": "artifacts/launch/bundles/public-alpha-local-demo.json"
}
```

Console read endpoints require `launch:read` when scopes are enabled. The public-alpha demo bundle endpoint requires `launch:export`. These endpoints are local-only and return replay/run metadata, fixture references, release evidence summaries, demo commands, and GPU evidence status without external model calls, provider-network calls, real funds, private keys, broadcasts, or settlement execution.
