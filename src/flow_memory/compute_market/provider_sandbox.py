"""Deterministic provider sandbox server for quote-contract conformance tests."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping

from flow_memory.compute_market.storage import deterministic_id, utc_now_iso


def sandbox_quote(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    profile = request.get("profile", {}) if isinstance(request.get("profile"), Mapping) else {}
    task_hash = str(profile.get("task_hash") or deterministic_id("sandbox_task", profile))
    quote_id = deterministic_id("sandbox_quote", {"task_hash": task_hash, "provider_id": "sandbox-provider"})
    return {
        "quote_id": quote_id,
        "provider_id": "sandbox-provider",
        "provider_or_route": "Flow Memory Sandbox Provider",
        "provider_type": "gpu",
        "route_id": "sandbox-gpu-route",
        "market_type": "marketplace",
        "unit_type": "gpu_minute",
        "unit_price": 0.09,
        "estimated_units": 2.0,
        "estimated_total_cost": 0.18,
        "currency_or_asset": "USDC",
        "payment_asset": "USDC",
        "network": "offchain",
        "confidence": 0.9,
        "capacity_available": True,
        "quote_ttl_seconds": 300,
        "expires_at": "2099-01-01T00:00:00Z",
        "settlement_modes": ("generic_dry_run",),
        "dry_run_supported": True,
        "dry_run_only": True,
        "funds_moved": False,
        "broadcast_allowed": False,
        "private_key_required": False,
        "assumptions": ("sandbox deterministic quote only",),
        "created_at": utc_now_iso(),
    }


def sandbox_health() -> dict[str, Any]:
    return {
        "ok": True,
        "provider_id": "sandbox-provider",
        "status": "healthy",
        "capacity_available": True,
        "dry_run_only": True,
        "funds_moved": False,
        "broadcast_allowed": False,
        "private_key_required": False,
        "checked_at": utc_now_iso(),
    }


def create_provider_sandbox_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "FlowMemoryProviderSandbox/0.1"

        def log_message(self, _format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802 - stdlib API
            if self.path == "/health":
                self._send({"ok": True, "health": sandbox_health()})
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802 - stdlib API
            if self.path != "/quote":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("content-length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                payload = {}
            if not isinstance(payload, Mapping):
                payload = {}
            self._send({"ok": True, "quote": sandbox_quote(payload)})

        def _send(self, payload: Mapping[str, Any]) -> None:
            body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Flow Memory Compute Market provider sandbox")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args(argv)
    server = create_provider_sandbox_server(str(args.host), int(args.port))
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
