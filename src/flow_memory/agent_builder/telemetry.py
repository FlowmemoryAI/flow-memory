"""Agent Builder visual telemetry event helpers."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.cognition.state import stable_id, utc_now

FORGE_EVENT_TYPES = (
    "agent_builder_defaults_loaded",
    "agent_builder_assembly_plan_created",
    "agent_builder_agent_born",
    "agent_builder_identity_published",
    "agent_builder_skill_match_simulated",
    "agent_builder_capability_upgrade_simulated",
    "agent_builder_mission_control_handoff",
)


def agent_builder_event(event_type: str, agent_id: str = "", payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if event_type not in FORGE_EVENT_TYPES:
        raise ValueError(f"unknown Agent Builder event type: {event_type}")
    body = dict(payload or {})
    return {
        "event_id": stable_id("agent_builder_event", event_type, agent_id, body),
        "event_type": event_type,
        "agent_id": agent_id,
        "payload": body,
        "created_at": utc_now(),
    }


__all__ = ["FORGE_EVENT_TYPES", "agent_builder_event"]
