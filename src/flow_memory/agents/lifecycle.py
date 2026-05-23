"""Agent lifecycle helpers."""

from __future__ import annotations

from flow_memory.agents.state import AgentState


def start_agent(state: AgentState) -> None:
    state.lifecycle_status = "running"
    state.add_event({"event": "agent_started"})


def stop_agent(state: AgentState) -> None:
    state.lifecycle_status = "stopped"
    state.add_event({"event": "agent_stopped"})


def fail_agent(state: AgentState, error: str) -> None:
    state.lifecycle_status = "failed"
    state.error_state = error
    state.health.ok = False
    state.health.failures += 1
    state.add_event({"event": "agent_failed", "error": error})
