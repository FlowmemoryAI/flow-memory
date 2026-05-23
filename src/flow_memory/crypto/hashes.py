"""Canonical JSON and hash helpers."""

from __future__ import annotations

from typing import Any

from flow_memory.crypto.canonical_json import canonical_json, canonical_json_hash


def content_hash(value: Any) -> str:
    return canonical_json_hash(value)
