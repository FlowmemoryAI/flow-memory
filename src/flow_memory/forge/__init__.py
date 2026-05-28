"""Flow Memory Forge browser agent builder and capability composer."""
from flow_memory.forge.core import (
    CAPABILITY_CARDS,
    DEFAULT_AGENT_NAME,
    DEFAULT_PURPOSE,
    ForgeAgentAssemblyPlan,
    birth_agent_from_forge,
    create_forge_assembly_plan,
    forge_defaults,
    publish_forge_agent_identity,
    simulate_forge_upgrades,
)

__all__ = [
    "CAPABILITY_CARDS",
    "DEFAULT_AGENT_NAME",
    "DEFAULT_PURPOSE",
    "ForgeAgentAssemblyPlan",
    "birth_agent_from_forge",
    "create_forge_assembly_plan",
    "forge_defaults",
    "publish_forge_agent_identity",
    "simulate_forge_upgrades",
]
