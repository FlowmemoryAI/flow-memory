from flow_memory.rl.envs.swarm_delegation_env import SwarmDelegationEnv


def test_swarm_delegation_env_deterministic_success_action():
    env=SwarmDelegationEnv(seed=3)
    first=env.step(env.action_labels.index("delegate_high_rep"))
    env.reset(seed=3)
    second=env.step(env.action_labels.index("delegate_high_rep"))
    assert first.reward == second.reward
    assert first.info
