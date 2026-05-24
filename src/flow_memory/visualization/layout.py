"""Deterministic 3D layout helpers for Mission Control."""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin, tau
from typing import Any, Mapping, Sequence

ROLE_ANCHORS: Mapping[str, tuple[float, float, float]] = {
    "requester": (-4.0, 0.0, 0.0),
    "worker": (0.0, 0.0, 0.0),
    "verifier": (4.0, 0.0, 0.0),
    "auditor": (0.0, 0.0, -3.0),
    "observer": (0.0, 0.0, -3.0),
    "agent": (0.0, 0.0, 3.0),
}


@dataclass(frozen=True)
class VisualLayout:
    positions: Mapping[str, tuple[float, float, float]]
    seed: int = 0
    layout_version: str = "mission-control-layout-v1"

    def as_record(self) -> Mapping[str, Any]:
        return {"layout_version": self.layout_version, "seed": self.seed, "positions": {key: tuple(value) for key, value in self.positions.items()}}


def deterministic_agent_layout(agents: Sequence[Mapping[str, Any]], *, seed: int = 0) -> VisualLayout:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for agent in agents:
        groups.setdefault(str(agent.get("role", "agent")), []).append(agent)
    positions: dict[str, tuple[float, float, float]] = {}
    for role, members in sorted(groups.items()):
        anchor = ROLE_ANCHORS.get(role, ROLE_ANCHORS["agent"])
        radius = 0.8 if len(members) > 1 else 0.0
        for index, agent in enumerate(sorted(members, key=lambda item: str(item.get("agent_id") or item.get("id") or item.get("label")))):
            angle = tau * index / max(1, len(members)) + seed * 0.001
            agent_id = str(agent.get("agent_id") or agent.get("id") or agent.get("label"))
            positions[agent_id] = (round(anchor[0] + radius * cos(angle), 4), round(anchor[1] + index * 0.2, 4), round(anchor[2] + radius * sin(angle), 4))
    return VisualLayout(positions=positions, seed=seed)


def apply_layout_to_state(state: Mapping[str, Any], *, seed: int = 0) -> Mapping[str, Any]:
    agents = tuple(dict(agent) for agent in state.get("agents", ()) if isinstance(agent, Mapping))
    layout = deterministic_agent_layout(agents, seed=seed)
    positioned = []
    for agent in agents:
        agent_id = str(agent.get("agent_id") or agent.get("id") or agent.get("label"))
        positioned.append({**agent, "position": layout.positions.get(agent_id, (0.0, 0.0, 0.0))})
    return {**dict(state), "agents": tuple(positioned), "layout": layout.as_record()}
