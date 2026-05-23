"""Canonical JSON and hash helpers."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Mapping


def canonical_json(value: Any) -> str:
    return json.dumps(_safe(value), sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if hasattr(value, "as_record"):
        return _safe(value.as_record())
    return value
