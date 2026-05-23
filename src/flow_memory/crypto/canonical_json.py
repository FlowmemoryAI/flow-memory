"""Deterministic JSON serialization for hashes and signatures."""

from __future__ import annotations

import json
from dataclasses import is_dataclass, asdict
from hashlib import sha256
from math import isfinite
from typing import Any, Mapping


class CanonicalJsonError(TypeError):
    """Raised when a value cannot be represented as canonical JSON."""


def canonical_json(value: Any) -> str:
    """Return stable, whitespace-free JSON suitable for hashing and signing.

    This is intentionally stricter than ``json.dumps`` defaults: object keys must
    already be strings, non-finite floats are rejected, and custom objects must
    expose ``as_record`` or be dataclasses.
    """

    return json.dumps(
        _safe(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Return UTF-8 bytes for the canonical JSON representation."""

    return canonical_json(value).encode("utf-8")


def canonical_json_hash(value: Any) -> str:
    """Return a SHA-256 hex digest of the canonical JSON representation."""

    return sha256(canonical_json_bytes(value)).hexdigest()


def _safe(value: Any) -> Any:
    if hasattr(value, "as_record"):
        return _safe(value.as_record())
    if is_dataclass(value) and not isinstance(value, type):
        return _safe(asdict(value))
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalJsonError(f"canonical JSON object keys must be strings, got {type(key).__name__}")
            safe[key] = _safe(item)
        return safe
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, float):
        if not isfinite(value):
            raise CanonicalJsonError("canonical JSON does not allow NaN or Infinity")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise CanonicalJsonError(f"value of type {type(value).__name__} is not canonical JSON serializable")
