"""Environment-driven HTTP API server entry point for live planning deployments."""
from __future__ import annotations

import argparse
import os
import json
import sys
from collections.abc import Mapping, Sequence

from flow_memory.api.http_server import HttpApiConfig, serve_local_api

_PUBLIC_BIND_HOSTS = frozenset({"0.0.0.0", "::", ""})


def build_http_api_config(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> HttpApiConfig:
    """Build an HTTP API config from CLI args plus deployment environment.

    The dependency-free HTTP server is still a minimal API boundary; for any
    non-local bind it must be placed behind TLS/ingress and use API-key plus
    scope enforcement.
    """

    source = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="Run the Flow Memory HTTP API server")
    parser.add_argument("--host", default=source.get("FLOW_MEMORY_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=_int(source.get("FLOW_MEMORY_API_PORT"), 8765))
    parser.add_argument("--api-key", default=source.get("FLOW_MEMORY_API_KEY", ""))
    api_key_records = _api_key_records(source.get("FLOW_MEMORY_API_KEYS_JSON", ""))
    parser.add_argument(
        "--require-scopes",
        action="store_true",
        default=_bool(source.get("FLOW_MEMORY_API_REQUIRE_SCOPES"), False),
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=_int(source.get("FLOW_MEMORY_API_RATE_LIMIT"), 120),
    )
    parser.add_argument(
        "--rate-limit-window-seconds",
        type=int,
        default=_int(source.get("FLOW_MEMORY_API_RATE_LIMIT_WINDOW_SECONDS"), 60),
    )
    parser.add_argument(
        "--max-body-bytes",
        type=int,
        default=_int(source.get("FLOW_MEMORY_API_MAX_BODY_BYTES"), 1_048_576),
    )
    parser.add_argument(
        "--enable-nonce-check",
        action="store_true",
        default=_bool(source.get("FLOW_MEMORY_API_ENABLE_NONCE_CHECK"), False),
    )
    parser.add_argument(
        "--max-request-age-seconds",
        type=int,
        default=_int(source.get("FLOW_MEMORY_API_MAX_REQUEST_AGE_SECONDS"), 300),
    )
    parser.add_argument(
        "--allow-unauthenticated-public-bind",
        action="store_true",
        help="Allow a non-local bind without FLOW_MEMORY_API_KEY; only safe behind an authenticated private proxy.",
    )
    args = parser.parse_args(list(argv or ()))
    config = HttpApiConfig(
        host=str(args.host),
        port=int(args.port),
        api_key=str(args.api_key),
        api_key_records=api_key_records,
        require_scopes=bool(args.require_scopes),
        rate_limit=int(args.rate_limit),
        rate_limit_window_seconds=int(args.rate_limit_window_seconds),
        max_body_bytes=int(args.max_body_bytes),
        enable_nonce_check=bool(args.enable_nonce_check),
        max_request_age_seconds=int(args.max_request_age_seconds),
    )
    errors = config.validate()
    if errors:
        parser.error("; ".join(errors))
    if _public_bind(config.host) and not config.api_key and not config.api_key_records and not bool(args.allow_unauthenticated_public_bind):
        parser.error("FLOW_MEMORY_API_KEY or --api-key is required when binding the API server to a non-local host")
    return config


def main(argv: Sequence[str] | None = None) -> int:
    config = build_http_api_config(sys.argv[1:] if argv is None else argv)
    print(f"Flow Memory API listening on http://{config.host}:{config.port}")
    serve_local_api(config)
    return 0


def _public_bind(host: str) -> bool:
    normalized = host.strip().lower()
    return normalized in _PUBLIC_BIND_HOSTS or normalized not in {"127.0.0.1", "localhost", "::1"}


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)



def _api_key_records(value: str | None) -> tuple[Mapping[str, object], ...]:
    if value is None or not value.strip():
        return ()
    decoded = json.loads(value)
    if not isinstance(decoded, list):
        raise ValueError("FLOW_MEMORY_API_KEYS_JSON must be a JSON array")
    records: list[Mapping[str, object]] = []
    for item in decoded:
        if not isinstance(item, Mapping):
            raise ValueError("FLOW_MEMORY_API_KEYS_JSON entries must be objects")
        records.append(item)
    return tuple(records)

if __name__ == "__main__":
    raise SystemExit(main())
