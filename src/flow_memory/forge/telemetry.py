"""Forge visual telemetry event helpers."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.cognition.state import stable_id, utc_now

FORGE_EVENT_TYPES = (
    "forge_defaults_loaded",
    "forge_assembly_plan_created",
    "forge_agent_born",
    "forge_identity_published",
    "forge_skill_match_simulated",
    "forge_capability_upgrade_simulated",
    "forge_mission_control_handoff",
)


def forge_event(event_type: str, agent_id: str = "", payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if event_type not in FORGE_EVENT_TYPES:
        raise ValueError(f"unknown Forge event type: {event_type}")
    body = dict(payload or {})
    return {
        "event_id": stable_id("forge_event", event_type, agent_id, body),
        "event_type": event_type,
        "agent_id": agent_id,
        "payload": body,
        "created_at": utc_now(),
    }


__all__ = ["FORGE_EVENT_TYPES", "forge_event"]
