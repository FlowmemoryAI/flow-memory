"""Launch integration for born agents."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from flow_memory.agent_genesis.genome import genome_to_agent_profile, get_genome
from flow_memory.agents.runner import AgentRunner


def run_born_agent(agent_id: str, goal: str = "", *, root: str | Path = ".") -> Mapping[str, Any]:
    genome = get_genome(agent_id, root=root)
    profile = genome_to_agent_profile(genome, name=str(genome.get("agent_id", agent_id)))
    result = AgentRunner(profile).run_cycle(goal or str(genome.get("purpose", "Explore and report")))
    return {"ok": True, "agent_id": agent_id, "result": result.as_record(), "safety_authority": "policy_engine_and_approval_gate"}
