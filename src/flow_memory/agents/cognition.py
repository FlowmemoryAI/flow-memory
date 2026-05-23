"""Agent cognition facade."""

from __future__ import annotations

from flow_memory.agents.planner import CognitivePlanner, Plan
from flow_memory.agents.profile import AgentProfile


class AgentCognition:
    def __init__(self, planner: CognitivePlanner | None = None) -> None:
        self.planner = planner or CognitivePlanner()

    def plan(self, profile: AgentProfile, goal: str) -> Plan:
        return self.planner.create_plan(goal, allowed_skills=profile.allowed_skills, allowed_tools=profile.allowed_tools)
