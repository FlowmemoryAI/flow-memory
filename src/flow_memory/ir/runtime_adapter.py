"""FlowIR runtime adapters."""

from __future__ import annotations

from typing import Any, Mapping, cast

from flow_memory.agents.profile import AgentProfile
from flow_memory.runtime import (
    AgentRuntimeManager,
    BaseRuntimeManager,
    EconomyRuntimeManager,
    MemoryRuntimeManager,
    PolicyRuntimeManager,
    RuntimeOrchestrator,
    SkillRuntimeManager,
)


def runtime_for_agent(_profile: AgentProfile) -> RuntimeOrchestrator:
    managers: Mapping[str, BaseRuntimeManager] = {
        "agent": cast(BaseRuntimeManager, AgentRuntimeManager()),
        "skills": SkillRuntimeManager(),
        "memory": MemoryRuntimeManager(),
        "economy": EconomyRuntimeManager(),
        "policy": PolicyRuntimeManager(),
    }
    orchestrator = RuntimeOrchestrator(managers=managers)
    orchestrator.start_all()
    return orchestrator


def runtime_summary(profile: AgentProfile) -> Mapping[str, Any]:
    runtime = runtime_for_agent(profile)
    health = runtime.health()
    return {"agent_id": profile.agent_id, "runtime": {"status": "ok" if health.ok else "degraded", "running": health.running, "checks": dict(health.checks)}}
