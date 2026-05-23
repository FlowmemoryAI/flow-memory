"""Optional LangGraph adapter skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flow_memory.core.loop import CognitiveLoop


@dataclass
class LangGraphLoopAdapter:
    loop: CognitiveLoop

    def build_graph(self) -> Any:
        try:
            from langgraph.graph import StateGraph  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install flow-memory[langgraph] to use LangGraphLoopAdapter") from exc
        # The concrete graph is intentionally small; production users can expand each
        # cognitive phase into a node while preserving the typed loop contracts.
        return StateGraph(dict)
