"""Agent plan executor."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.agents.planner import Plan, PlanStep
from flow_memory.agents.skill_binding import AgentSkillBinding
from flow_memory.agents.tool_binding import AgentToolBinding


class AgentExecutor:
    def __init__(self, skills: AgentSkillBinding | None = None, tools: AgentToolBinding | None = None) -> None:
        self.skills = skills or AgentSkillBinding()
        self.tools = tools or AgentToolBinding()

    def execute(self, plan: Plan, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        results: list[Mapping[str, Any]] = []
        for step in plan.steps:
            results.append(self.execute_step(step, payload))
        success = all(bool(result.get("success", False)) for result in results)
        return {"success": success, "output": results[-1].get("output") if results else None, "step_results": tuple(results)}

    def execute_step(self, step: PlanStep, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if step.required_skills:
            return self.skills.run_skill(step.required_skills[0], payload)
        tool = step.required_tools[0] if step.required_tools else "respond"
        return self.tools.run_tool(tool, payload)
