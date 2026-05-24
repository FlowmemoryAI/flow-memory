from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.agents import AgentProfile, AgentRunner
from flow_memory.rl.envs.safety_gate_env import SafetyGateEnv
from flow_memory.rl.trainer import SimpleQLearningTrainer


def run_demo() -> dict[str, object]:
    env = SafetyGateEnv(seed=19, max_steps=3)
    trainer = SimpleQLearningTrainer(env)
    training = trainer.train(episodes=20)
    profile = AgentProfile(
        name="RL Advisory Agent",
        identity="did:flow:rl-launch-agent",
        goals=("Choose a safe plan",),
        capabilities=("safe_tool_use", "rl_advisory"),
        allowed_tools=("observe_environment", "respond"),
        autonomy_mode="supervised",
        rl_config={"enabled": True, "backend": "local_tabular", "training_envs": ("safety_gate",), "safety_authority": "policy_engine"},
    )
    result = AgentRunner(profile).run_cycle("Choose a safe plan")
    return {
        "ok": bool(training.improved and (result.accepted or result.requires_approval)),
        "launch_mode": "rl_trained_agent",
        "training": training.as_record(),
        "rl_metadata": result.output.get("rl", {}),
        "safety_authority": "policy_engine_and_approval_gate",
        "rl_can_bypass_safety": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True, default=str))
