"""Check local dashboard snapshot API endpoint without starting a server."""
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


def check_dashboard_api(*, require_scopes: bool = False) -> dict[str, object]:
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only" if require_scopes else "", require_scopes=require_scopes, enable_rate_limit=False))
    headers = {"x-flow-memory-scopes": "dashboard:read"}
    if require_scopes:
        headers["x-flow-memory-api-key"] = "dev-local-only"
    response = gateway.handle("GET", "/dashboard/snapshot", headers)
    data = dict(response.body.get("data", {}))
    records = dict(data.get("records", {}))
    return {
        "ok": response.status == 200 and data.get("ok") is True and data.get("mock_data_only") is True,
        "status": response.status,
        "record_count": len(records),
        "records": tuple(sorted(records)),
        "mock_data_only": bool(data.get("mock_data_only")),
        "raw_artifacts_exposed": bool(data.get("raw_artifacts_exposed", True)),
        "requires_network_server": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Flow Memory dashboard API endpoint")
    parser.add_argument("--require-scopes", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    payload = check_dashboard_api(require_scopes=args.require_scopes)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["ok"] and not payload["raw_artifacts_exposed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
