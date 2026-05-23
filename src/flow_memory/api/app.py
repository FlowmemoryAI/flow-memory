"""Optional ASGI/FastAPI application boundary."""
from __future__ import annotations

from flow_memory.api.router import create_default_router


def create_app():
    """Return a FastAPI app when FastAPI is installed, otherwise return the local router."""
    router = create_default_router()
    try:
        from fastapi import FastAPI  # type: ignore
    except Exception:
        return router

    app = FastAPI(title="Flow Memory Local API", version="0.3.0")

    @app.get("/health")
    def health():
        return router.dispatch("GET", "/health")

    @app.get("/manifest")
    def manifest():
        return router.dispatch("GET", "/manifest")

    return app
