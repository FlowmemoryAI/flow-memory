"""Agent tool binding."""

from __future__ import annotations

from typing import Any, Mapping


class AgentToolBinding:
    def run_tool(self, tool: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if tool == "respond":
            return {"success": True, "tool": tool, "output": str(payload.get("message", payload.get("goal", "")))}
        return {"success": True, "tool": tool, "output": dict(payload)}
