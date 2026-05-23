"""Layered memory composition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import MemoryRecord, PerceptionOutput, Prediction
from flow_memory.memory.economic import EconomicMemory
from flow_memory.memory.episodic import EpisodicMemory
from flow_memory.memory.procedural import ProceduralSkill, SkillLibrary
from flow_memory.memory.semantic import SemanticGraph
from flow_memory.memory.working import WorkingMemory


@dataclass
class MemorySystem:
    """Composes working, episodic, semantic, procedural, and economic memory."""

    working: WorkingMemory = field(default_factory=WorkingMemory)
    episodic: EpisodicMemory = field(default_factory=EpisodicMemory)
    semantic: SemanticGraph = field(default_factory=SemanticGraph)
    procedural: SkillLibrary = field(default_factory=SkillLibrary)
    economic: EconomicMemory = field(default_factory=EconomicMemory)

    def observe(
        self,
        text: str,
        kind: str = "observation",
        payload: Mapping[str, Any] | None = None,
        importance: float = 0.55,
    ) -> MemoryRecord:
        record = self.episodic.record(kind=kind, text=text, payload=payload or {}, importance=importance)
        self.working.put(record)
        return record

    def retrieve_relevant(
        self,
        perception: PerceptionOutput,
        prediction: Prediction,
        limit: int = 5,
    ) -> tuple[MemoryRecord, ...]:
        entity_text = " ".join(entity.label for entity in perception.entities)
        affordance_text = " ".join(perception.motion_geometry.affordances)
        predicted_text = " ".join(map(str, prediction.state.get("expected_affordances", [])))
        query = f"{entity_text} {affordance_text} {predicted_text}".strip()
        if not query:
            return self.working.snapshot()[-limit:]
        retrieved = self.episodic.retrieve(query=query, limit=limit)
        if retrieved:
            return retrieved
        return self.working.snapshot()[-limit:]

    def consolidate_perception(self, perception: PerceptionOutput) -> None:
        for entity in perception.entities:
            self.semantic.add_node(entity.label, kind="entity", confidence=entity.confidence)
        for affordance in perception.motion_geometry.affordances:
            self.semantic.add_node(affordance, kind="affordance")
            for entity in perception.entities:
                self.semantic.add_fact(entity.label, "affords", affordance)
