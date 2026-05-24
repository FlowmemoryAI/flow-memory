"""Prototype memory-learning helpers.

This is local memory accumulation and retrieval, not trained neural learning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.learning.trace_collector import AgentLearningTrace


@dataclass
class MemoryLearningStore:
    traces: list[AgentLearningTrace] = field(default_factory=list)

    def add_trace(self, trace: AgentLearningTrace) -> None:
        self.traces.append(trace)

    def retrieve(self, query: str, *, limit: int = 3) -> tuple[Mapping[str, Any], ...]:
        terms = {part.lower() for part in query.split() if part.strip()}
        scored: list[tuple[int, AgentLearningTrace]] = []
        for trace in self.traces:
            haystack = f"{trace.goal} {trace.as_record()}".lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, trace))
        scored.sort(key=lambda item: item[0], reverse=True)
        return tuple(trace.as_record() for _, trace in scored[:limit])

    def report(self) -> Mapping[str, Any]:
        success_count = sum(1 for trace in self.traces if trace.success())
        return {"trace_count": len(self.traces), "success_count": success_count, "memory_learning": "episodic traces improve future retrieval context"}
