# Visual API

The local dependency-free API server exposes Mission Control telemetry without requiring a frontend build.

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765
```

Endpoints:

- `GET /visual/state` — current reduced `VisualNetworkState` from local network scenarios.
- `GET /visual/events` — current visual event list.
- `GET /visual/schema` — visual schema/version metadata.
- `GET /visual/replay/{run_id}` — saved visual replay artifact.
- `GET /network/state` — local network report plus visual projection.
- `POST /network/run-scenario` — run a local scenario; pass `emit_visual_events: true` for visual output.
- `POST /visual/replay/start` — run a scenario and save a replay under `artifacts/visual/`.

Scopes:

- `visual:read` for visual reads.
- `network:run` for scenario execution.

These endpoints are local public-alpha infrastructure, not a production-hosted API.
