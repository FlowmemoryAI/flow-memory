"""Run the dependency-free Flow Memory local HTTP API server."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.api.http_server import HttpApiConfig, serve_local_api


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Flow Memory local HTTP API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--require-scopes", action="store_true")
    parser.add_argument("--rate-limit", type=int, default=120)
    args = parser.parse_args()
    config = HttpApiConfig(
        host=args.host,
        port=args.port,
        api_key=args.api_key,
        require_scopes=args.require_scopes,
        rate_limit=args.rate_limit,
    )
    print(f"Flow Memory local API listening on http://{config.host}:{config.port}")
    serve_local_api(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
