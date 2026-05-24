"""Check local release evidence API endpoints without starting a network server."""
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


def check_release_api(*, require_scopes: bool = False) -> dict[str, object]:
    gateway = HttpApiGateway(config=HttpApiConfig(api_key="dev-local-only" if require_scopes else "", require_scopes=require_scopes, enable_rate_limit=False))
    headers = {"x-flow-memory-scopes": "release:read"}
    if require_scopes:
        headers["x-flow-memory-api-key"] = "dev-local-only"
    evidence = gateway.handle("GET", "/release/evidence", headers)
    decision = gateway.handle("GET", "/release/decision/local", headers)
    payload = {
        "ok": evidence.status == 200 and decision.status == 200,
        "evidence_status": evidence.status,
        "decision_status": decision.status,
        "evidence": evidence.body.get("data", {}),
        "decision": decision.body.get("data", {}),
        "raw_artifacts_exposed": bool(dict(evidence.body.get("data", {})).get("raw_artifacts_exposed", True)),
        "requires_network_server": False,
    }
    payload["ok"] = bool(payload["ok"] and payload["raw_artifacts_exposed"] is False)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Flow Memory release API endpoints")
    parser.add_argument("--require-scopes", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    payload = check_release_api(require_scopes=args.require_scopes)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
