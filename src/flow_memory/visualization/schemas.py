"""Machine-readable Mission Control visual schema."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.visualization.events import VISUAL_SCHEMA_VERSION


def visual_schema() -> Mapping[str, Any]:
    return {
        "schema_version": VISUAL_SCHEMA_VERSION,
        "provenance_values": ("live", "replay", "mock", "synthetic"),
        "event_types": ("agent", "task", "memory", "economy", "compute", "supervisor", "neural", "cognitive", "internet", "rl", "safety", "audit"),
        "state_collections": ("agents", "tasks", "memory", "economy", "compute", "supervisor", "neural", "cognitive", "internet", "rl", "safety", "audit"),
        "neural_live_fields": ("session_id", "phase", "prediction_confidence", "uncertainty", "learning_tick_count", "memory_activation_count", "action_state", "policy_gate_state"),
        "predictive_cognitive_fields": ("prediction_id", "chosen_action", "predicted_outcome", "actual_result", "prediction_error", "lesson", "future_policy"),
        "agent_internet_fields": ("network_agent_id", "skill_manifest_id", "match_id", "collaboration_session_id", "workspace_id", "reputation_score", "payment_rail", "adapter_mode"),
        "supervisor_fields": ("supervisor_id", "run_id", "status", "current_phase", "ticks_completed", "max_ticks", "policy_gate_state", "last_heartbeat_at", "bounded"),
        "required_reference": "source_event_id when available",
    }
