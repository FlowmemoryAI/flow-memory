# API Agent Launch Endpoints

The dependency-free local API server now exposes public-alpha launch endpoints:

| Method | Path | Scope when enabled | Purpose |
| --- | --- | --- | --- |
| POST | `/agents/launch` | `agents:launch` | Launch a local AgentProfile/AgentRunner cycle. |
| POST | `/agents/launch-flowlang` | `agents:launch` | Compile and run FlowLang source. |
| POST | `/agents/launch-neural` | `agents:launch` | Launch an agent with neural advisory metadata. |
| POST | `/network/run-scenario` | `network:run` | Run a local network scenario. |

Example with local API-key/scopes:

```bash
python scripts/run_local_api_server.py --api-key dev-local-only --require-scopes
```

Send `X-Flow-Memory-API-Key: dev-local-only` and `X-Flow-Memory-Scopes: agents:launch` for agent launch calls.

These endpoints are local/public-alpha seams, not production internet auth or hosted orchestration.
