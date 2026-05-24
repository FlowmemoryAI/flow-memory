"""Flow Arena environment registry."""
from __future__ import annotations
from typing import Callable
from flow_memory.rl.env import FlowEnv
_FACTORIES: dict[str, Callable[..., FlowEnv]] = {}

def register_env(name: str, factory: Callable[..., FlowEnv]) -> None:
    _FACTORIES[name]=factory

def make_env(name: str, **kwargs) -> FlowEnv:
    register_default_envs()
    if name not in _FACTORIES: raise KeyError(f"unknown Flow Arena env: {name}")
    return _FACTORIES[name](**kwargs)

def env_names() -> tuple[str,...]:
    register_default_envs(); return tuple(sorted(_FACTORIES))

def register_default_envs() -> None:
    if _FACTORIES: return
    from flow_memory.rl.envs.tool_use_env import ToolUseEnv
    from flow_memory.rl.envs.memory_retrieval_env import MemoryRetrievalEnv
    from flow_memory.rl.envs.economy_market_env import EconomyMarketEnv
    from flow_memory.rl.envs.verifier_env import VerifierEnv
    from flow_memory.rl.envs.swarm_delegation_env import SwarmDelegationEnv
    from flow_memory.rl.envs.safety_gate_env import SafetyGateEnv
    from flow_memory.rl.envs.self_repair_env import SelfRepairEnv
    from flow_memory.rl.envs.gridworld import GridWorld
    from flow_memory.rl.envs.reputation_gaming_env import ReputationGamingEnv
    from flow_memory.rl.envs.sybil_risk_env import SybilRiskEnv
    from flow_memory.rl.envs.colluding_verifier_env import ColludingVerifierEnv
    for cls in (ToolUseEnv, MemoryRetrievalEnv, EconomyMarketEnv, VerifierEnv, SwarmDelegationEnv, SafetyGateEnv, SelfRepairEnv, GridWorld, ReputationGamingEnv, SybilRiskEnv, ColludingVerifierEnv):
        register_env(cls.env_id, cls)
