"""Deterministic provider sandbox server for quote-contract conformance tests."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping

from flow_memory.compute_market.storage import deterministic_id, utc_now_iso
from flow_memory.crypto.hashes import content_hash
from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import verify_payload


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


def sandbox_execute(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    job = request.get("job", {}) if isinstance(request.get("job"), Mapping) else {}
    job_id = str(job.get("job_id") or deterministic_id("sandbox_job", job))
    execution_id = deterministic_id("sandbox_execution", {"job_id": job_id, "provider_id": "sandbox-provider"})
    return {
        "execution_id": execution_id,
        "provider_job_id": execution_id,
        "job_id": job_id,
        "provider_id": "sandbox-provider",
        "status": "running",
        "artifact_ref": "",
        "artifact_data": {},
        "actual_units": 0.0,
        "actual_total_cost": 0.0,
        "actual_latency_ms": 0.0,
        "dry_run_only": True,
        "funds_moved": False,
        "broadcast_allowed": False,
        "private_key_required": False,
        "accepted_at": utc_now_iso(),
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


def create_provider_sandbox_server(host: str = "127.0.0.1", port: int = 0, *, signing_key: LocalKeyPair | None = None) -> ThreadingHTTPServer:
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
            if self.path not in {"/quote", "/execute"}:
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
            if signing_key is not None and not verify_provider_sandbox_request(
                self.headers,
                payload,
                signing_key=signing_key,
                kind="execution" if self.path == "/execute" else "quote",
            ):
                self._send(
                    {
                        "ok": False,
                        "error": {
                            "error_code": "provider_sandbox.signature_invalid",
                            "message": "Provider sandbox request signature is missing or invalid.",
                        },
                    },
                    status=401,
                )
                return
            if self.path == "/execute":
                self._send({"ok": True, "execution": sandbox_execute(payload)})
                return
            self._send({"ok": True, "quote": sandbox_quote(payload)})

        def _send(self, payload: Mapping[str, Any], *, status: int = 200) -> None:
            body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, port), Handler)


def verify_provider_sandbox_request(
    headers: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    signing_key: LocalKeyPair,
    kind: str,
) -> bool:
    signature_payload_raw = str(headers.get("x-flow-memory-provider-signature-payload", ""))
    signature_raw = str(headers.get("x-flow-memory-provider-signature", ""))
    if not signature_payload_raw or not signature_raw:
        return False
    try:
        signature_payload = json.loads(signature_payload_raw)
        envelope = json.loads(signature_raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(signature_payload, Mapping) or not isinstance(envelope, Mapping):
        return False
    if str(signature_payload.get("kind", "")) != kind:
        return False
    if str(signature_payload.get("payload_hash", "")) != content_hash(payload):
        return False
    if not str(signature_payload.get("timestamp", "")) or not str(signature_payload.get("nonce", "")):
        return False
    return verify_payload(signature_payload, envelope, signing_key)


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
