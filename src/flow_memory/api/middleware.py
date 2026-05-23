"""API middleware seams."""

from __future__ import annotations

from typing import Any, Mapping


def request_context(method: str, path: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return {"method": method.upper(), "path": path, "payload": dict(payload or {})}
