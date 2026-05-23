"""API manifest snapshot helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.api.manifest import API_ENDPOINTS, endpoint_manifest
from flow_memory.api.openapi import openapi_schema
from flow_memory.crypto.hashes import content_hash

SNAPSHOT_VERSION = "api-snapshot-v1"


@dataclass(frozen=True)
class ApiSnapshotValidation:
    ok: bool
    errors: tuple[str, ...] = ()

    def as_record(self) -> Mapping[str, Any]:
        return {"ok": self.ok, "errors": self.errors}


def api_snapshot() -> Mapping[str, Any]:
    """Return a deterministic API snapshot for CI/release checks."""

    manifest = endpoint_manifest()
    openapi = openapi_schema()
    paths = tuple(sorted({endpoint.path for endpoint in API_ENDPOINTS}))
    operations = tuple(sorted(f"{endpoint.method} {endpoint.path}" for endpoint in API_ENDPOINTS))
    return {
        "version": SNAPSHOT_VERSION,
        "endpoint_count": len(API_ENDPOINTS),
        "path_count": len(paths),
        "paths": paths,
        "operations": operations,
        "manifest_hash": content_hash(manifest),
        "openapi_hash": content_hash(openapi),
    }


def validate_api_snapshot(snapshot: Mapping[str, Any]) -> ApiSnapshotValidation:
    """Validate a stored snapshot against the current manifest/OpenAPI output."""

    current = api_snapshot()
    normalized = _normalize(snapshot)
    errors = tuple(
        f"{key} mismatch: expected {current.get(key)!r}, got {normalized.get(key)!r}"
        for key in ("version", "endpoint_count", "path_count", "paths", "operations", "manifest_hash", "openapi_hash")
        if normalized.get(key) != current.get(key)
    )
    return ApiSnapshotValidation(ok=not errors, errors=errors)


def _normalize(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        str(key): tuple(value) if key in {"paths", "operations"} and isinstance(value, list) else value
        for key, value in snapshot.items()
    }
