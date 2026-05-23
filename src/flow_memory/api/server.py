"""Optional API server seam."""

from __future__ import annotations


def create_app():
    try:
        from flow_memory.api.app import create_app as create_fastapi_app
    except Exception as exc:  # pragma: no cover - optional dependency seam
        raise RuntimeError("FastAPI app is optional; install FastAPI to create an ASGI server") from exc
    return create_fastapi_app()
