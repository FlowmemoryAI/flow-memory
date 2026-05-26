from flow_memory.rl.envs.tool_use_env import ToolUseEnv


def test_tool_use_env_deterministic_success_action() -> None:
    env=ToolUseEnv(seed=3)
    first=env.step(env.action_labels.index("use_safe_tool"))
    env.reset(seed=3)
    second=env.step(env.action_labels.index("use_safe_tool"))
    assert first.reward == second.reward
    assert first.info
