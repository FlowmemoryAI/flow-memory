from flow_memory.rl.envs.safety_gate_env import SafetyGateEnv


def test_safety_gate_env_deterministic_success_action() -> None:
    env=SafetyGateEnv(seed=3)
    first=env.step(env.action_labels.index("choose_safer_plan"))
    env.reset(seed=3)
    second=env.step(env.action_labels.index("choose_safer_plan"))
    assert first.reward == second.reward
    assert first.info
