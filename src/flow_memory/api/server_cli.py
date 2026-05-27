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
        "--nonce-replay-backend",
        default=source.get("FLOW_MEMORY_API_NONCE_REPLAY_BACKEND", "memory"),
        choices=("memory", "in_memory", "redis"),
    )
    parser.add_argument(
        "--nonce-redis-url",
        default=source.get("FLOW_MEMORY_API_NONCE_REDIS_URL") or source.get("FLOW_MEMORY_COMPUTE_REDIS_URL", ""),
    )
    parser.add_argument(
        "--nonce-redis-prefix",
        default=source.get("FLOW_MEMORY_API_NONCE_REDIS_PREFIX", "flow-memory:api"),
    )
    parser.add_argument(
        "--nonce-fail-open",
        action="store_true",
        default=not _bool(source.get("FLOW_MEMORY_API_NONCE_FAIL_CLOSED"), True),
    )
    parser.add_argument(
        "--nonce-require-tls",
        action="store_true",
        default=_bool(source.get("FLOW_MEMORY_API_NONCE_REQUIRE_TLS"), False),
    )
    parser.add_argument(
        "--nonce-skip-tls-verify",
        action="store_true",
        default=not _bool(source.get("FLOW_MEMORY_API_NONCE_VERIFY_TLS"), True),
    )
    parser.add_argument(
        "--provider-callback-ip-allowlist",
        default=source.get("FLOW_MEMORY_COMPUTE_PROVIDER_CALLBACK_IP_ALLOWLIST", ""),
        help="Comma-separated provider callback source IP/CIDR allowlist.",
    )
    parser.add_argument("--jwt-hs256-secret", default=source.get("FLOW_MEMORY_API_JWT_HS256_SECRET", ""))
    parser.add_argument("--jwt-issuer", default=source.get("FLOW_MEMORY_API_JWT_ISSUER", ""))
    parser.add_argument("--jwt-audience", default=source.get("FLOW_MEMORY_API_JWT_AUDIENCE", ""))
    parser.add_argument(
        "--jwt-leeway-seconds",
        type=int,
        default=_int(source.get("FLOW_MEMORY_API_JWT_LEEWAY_SECONDS"), 60),
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
        jwt_hs256_secret=str(args.jwt_hs256_secret),
        jwt_issuer=str(args.jwt_issuer),
        jwt_audience=str(args.jwt_audience),
        jwt_leeway_seconds=int(args.jwt_leeway_seconds),
        nonce_replay_backend=str(args.nonce_replay_backend),
        nonce_redis_url=str(args.nonce_redis_url),
        nonce_redis_prefix=str(args.nonce_redis_prefix),
        nonce_fail_closed=not bool(args.nonce_fail_open),
        nonce_require_tls=bool(args.nonce_require_tls),
        nonce_verify_tls=not bool(args.nonce_skip_tls_verify),
        provider_callback_ip_allowlist=_csv_tuple(str(args.provider_callback_ip_allowlist)),
    )
    errors = config.validate()
    if errors:
        parser.error("; ".join(errors))
    if (
        _public_bind(config.host)
        and not config.api_key
        and not config.api_key_records
        and not config.jwt_hs256_secret
        and not bool(args.allow_unauthenticated_public_bind)
    ):
        parser.error("FLOW_MEMORY_API_KEY, FLOW_MEMORY_API_KEYS_JSON, or FLOW_MEMORY_API_JWT_HS256_SECRET is required when binding the API server to a non-local host")
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


def _csv_tuple(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


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
