from flow_memory.rl.envs.self_repair_env import SelfRepairEnv


def test_self_repair_env_deterministic_success_action() -> None:
    env=SelfRepairEnv(seed=3)
    first=env.step(env.action_labels.index("disable_failing_skill"))
    env.reset(seed=3)
    second=env.step(env.action_labels.index("disable_failing_skill"))
    assert first.reward == second.reward
    assert first.info
