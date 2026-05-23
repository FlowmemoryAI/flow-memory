"""Agent facade."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from flow_memory.config import RuntimeConfig
from flow_memory.core.loop import CognitiveLoop
from flow_memory.core.types import CognitiveCycleResult, Observation
from flow_memory.memory.system import MemorySystem, ProceduralSkill, WorkingMemory
from flow_memory.safety.audit import ImmutableAuditLog
from flow_memory.safety.system import SafetySystem


@dataclass(frozen=True)
class AgentConfig:
    """Agent identity and runtime settings."""

    name: str
    capabilities: Sequence[str] = field(default_factory=tuple)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)


@dataclass
class Agent:
    """High-level API for a Flow Memory agent."""

    config: AgentConfig
    loop: CognitiveLoop = field(default_factory=CognitiveLoop)

    @classmethod
    def create(
        cls,
        name: str,
        capabilities: Sequence[str] | None = None,
        data_dir: str | Path | None = None,
    ) -> "Agent":
        runtime = RuntimeConfig(data_dir=Path(data_dir) if data_dir is not None else Path(".flow_memory"))
        config = AgentConfig(name=name, capabilities=tuple(capabilities or ()), runtime=runtime)
        memory = MemorySystem(working=WorkingMemory(capacity=runtime.max_working_memory_items))
        audit_path = runtime.audit_log_path
        safety = SafetySystem(audit=ImmutableAuditLog(path=audit_path))
        loop = CognitiveLoop(memory=memory, safety=safety)
        agent = cls(config=config, loop=loop)
        for capability in config.capabilities:
            agent.loop.memory.procedural.register(
                ProceduralSkill(
                    name=capability,
                    description=f"Declared capability: {capability}",
                    required_permission="tool.invoke",
                )
            )
        return agent

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def did(self) -> str:
        return self.loop.economy.identity.uri()

    def run_cycle(self, observation: Observation | str) -> CognitiveCycleResult:
        return self.loop.run(observation)

    def run(self, observation: Observation | str) -> str:
        cycle = self.run_cycle(observation)
        return str(cycle.final_output)
