"""Plan generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from flow_memory.core.types import MemoryRecord, Observation, PerceptionOutput, Plan, PlanStep, Prediction


@dataclass
class SimpleReasoner:
    """Deterministic conservative planner."""

    default_style: str = "concise"

    def generate_plan(
        self,
        observation: Observation,
        perception: PerceptionOutput,
        prediction: Prediction,
        memories: Sequence[MemoryRecord],
    ) -> Plan:
        prompt = observation.as_text()
        lower = prompt.lower()
        steps: list[PlanStep] = []

        if any(term in lower for term in ("explore", "inspect", "observe", "survey")):
            steps.append(
                PlanStep(
                    action="observe_environment",
                    args={
                        "mode": "safe_local_simulation",
                        "entities": [entity.label for entity in perception.entities],
                        "affordances": list(perception.motion_geometry.affordances),
                    },
                    required_permission="environment.observe",
                )
            )

        if any(term in lower for term in ("remember", "recall", "memory")) and memories:
            steps.append(
                PlanStep(
                    action="summarize_memories",
                    args={"limit": min(5, len(memories))},
                    required_permission="memory.read",
                )
            )

        economic_intent = any(term in lower for term in ("earn", "bid", "marketplace", "settle", "flow"))
        response_message = self._compose_response(prompt, perception, prediction, memories, economic_intent)
        steps.append(PlanStep(action="respond", args={"message": response_message}, required_permission="respond"))

        return Plan(
            goal=prompt,
            steps=tuple(steps),
            metadata={
                "perception_summary": perception.summary(),
                "prediction_confidence": prediction.confidence,
                "memory_count": len(memories),
                "economic_intent_detected": economic_intent,
            },
        )

    def _compose_response(
        self,
        prompt: str,
        perception: PerceptionOutput,
        prediction: Prediction,
        memories: Sequence[MemoryRecord],
        economic_intent: bool = False,
    ) -> str:
        entity_labels = [entity.label for entity in perception.entities]
        affordances = list(perception.motion_geometry.affordances)
        parts = [f"Processed goal: {prompt}"]
        if entity_labels:
            parts.append(f"Perceived entities: {', '.join(entity_labels)}")
        if affordances:
            parts.append(f"Available affordances: {', '.join(affordances)}")
        parts.append(f"Prediction confidence: {prediction.confidence:.2f}")
        if memories:
            parts.append(f"Retrieved memories: {len(memories)} relevant record(s)")
        if economic_intent:
            parts.append("Economic intent detected; settlement requires explicit marketplace plan approval")
        parts.append("Status: plan approved and executed in the local safety sandbox")
        return " | ".join(parts)


RuleBasedReasoner = SimpleReasoner
