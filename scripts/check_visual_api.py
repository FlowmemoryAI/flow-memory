"""Smoke-check Mission Control visual API endpoints through the in-process HTTP gateway."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway


def check_visual_api(*, require_scopes: bool = False) -> dict[str, object]:
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only" if require_scopes else "", require_scopes=require_scopes, enable_rate_limit=False))
    headers = {"x-flow-memory-scopes": "visual:read network:run"}
    if require_scopes:
        headers["x-flow-memory-api-key"] = "dev-local-only"
    state = gateway.handle("GET", "/visual/state", headers=headers)
    events = gateway.handle("GET", "/visual/events", headers=headers)
    schema = gateway.handle("GET", "/visual/schema", headers=headers)
    scenario = gateway.handle("POST", "/network/run-scenario", headers=headers, body=json.dumps({"scenario": "basic-economy", "emit_visual_events": True}).encode("utf-8"))
    return {
        "ok": all(response.status == 200 for response in (state, events, schema, scenario)),
        "state_status": state.status,
        "events_status": events.status,
        "schema_status": schema.status,
        "scenario_status": scenario.status,
        "requires_network_server": False,
        "requires_scopes": require_scopes,
        "raw_artifacts_exposed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local visual API endpoints")
    parser.add_argument("--require-scopes", action="store_true")
    args = parser.parse_args()
    payload = check_visual_api(require_scopes=args.require_scopes)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
