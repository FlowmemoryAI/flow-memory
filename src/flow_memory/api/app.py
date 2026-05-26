"""Optional ASGI/FastAPI application boundary."""
from __future__ import annotations

from typing import Any, Mapping, cast
from flow_memory.api.router import create_default_router


def create_app() -> object:
    """Return a FastAPI app when FastAPI is installed, otherwise return the local router."""
    router = create_default_router()
    try:
        from fastapi import FastAPI
    except Exception:
        return router

    app = FastAPI(title="Flow Memory Local API", version="0.3.0")

    def health() -> Mapping[str, Any]:
        return router.dispatch("GET", "/health")

    def manifest() -> Mapping[str, Any]:
        return router.dispatch("GET", "/manifest")

    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/manifest", manifest, methods=["GET"])

    return cast(object, app)
