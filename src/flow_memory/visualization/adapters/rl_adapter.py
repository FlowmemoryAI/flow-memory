"""RL telemetry adapter."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.visualization.events import VisualEvent, visual_event


def rl_record_to_visual_events(record: Mapping[str, Any], *, agent_id: str = "", provenance: str = "live") -> tuple[VisualEvent, ...]:
    metrics = dict(record.get("metrics", {})) if isinstance(record.get("metrics", {}), Mapping) else dict(record)
    return (visual_event("rl", str(record.get("episode_id") or record.get("env_id") or "rl"), {
        "episode_id": record.get("episode_id") or f"rl-{record.get('env_id', 'episode')}",
        "agent_id": agent_id or record.get("agent_id", ""),
        "env_id": record.get("env_id", metrics.get("env_id", "unknown")),
        "mean_reward": metrics.get("mean_reward", record.get("mean_reward", 0.0)),
        "success_rate": metrics.get("mean_success_rate", metrics.get("success_rate", 0.0)),
        "safety_violation_rate": metrics.get("mean_safety_violation_rate", metrics.get("safety_violation_rate", 0.0)),
        "policy": record.get("policy", "local_tabular"),
    }, provenance=provenance),)
