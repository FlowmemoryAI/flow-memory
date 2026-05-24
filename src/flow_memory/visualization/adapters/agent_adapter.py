"""Agent-to-visual telemetry adapter."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from flow_memory.visualization.events import VisualEvent, visual_event


def agent_participants_to_visual_events(participants: Iterable[Mapping[str, Any]], *, provenance: str = "live") -> tuple[VisualEvent, ...]:
    events: list[VisualEvent] = []
    for item in participants:
        card = dict(item.get("card", {})) if isinstance(item.get("card"), Mapping) else {}
        profile = dict(item.get("profile", {})) if isinstance(item.get("profile"), Mapping) else {}
        agent_id = str(card.get("did") or profile.get("identity") or profile.get("agent_id") or item.get("role", "agent"))
        events.append(visual_event("agent", agent_id, {
            "agent_id": agent_id,
            "label": str(card.get("name") or profile.get("name") or agent_id),
            "role": str(item.get("role", "agent")),
            "status": str(item.get("status", "idle")),
            "reputation": float(card.get("reputation", profile.get("reputation", 0.0)) or 0.0),
            "capabilities": tuple(card.get("capabilities", profile.get("capabilities", ())) or ()),
        }, provenance=provenance))
    return tuple(events)
