"""Optional FastAPI application factory."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from flow_memory import Agent


def create_app() -> Any:
    """Create a FastAPI app when ``fastapi`` is installed.

    The core package does not depend on FastAPI by default. Install deployment extras and
    call this function from an ASGI server for HTTP access.
    """

    try:
        from fastapi import FastAPI  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install FastAPI to use flow_memory.server.create_app") from exc

    app = FastAPI(title="Flow Memory", version="0.2.0")
    agent = Agent.create(name="server", capabilities=["perception", "memory", "reasoning"])

    @app.get("/health")
    def health() -> Mapping[str, Any]:
        return {"ok": True, "did": agent.did}

    @app.post("/run")
    def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        prompt = str(payload.get("prompt", ""))
        cycle = agent.run_cycle(prompt)
        return asdict(cycle)

    return app
