from flow_memory.rl.envs.verifier_env import VerifierEnv


def test_verifier_env_deterministic_success_action() -> None:
    env=VerifierEnv(seed=3)
    first=env.step(env.action_labels.index("request_evidence"))
    env.reset(seed=3)
    second=env.step(env.action_labels.index("request_evidence"))
    assert first.reward == second.reward
    assert first.info
