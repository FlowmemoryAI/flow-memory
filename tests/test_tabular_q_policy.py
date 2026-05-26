from flow_memory.rl.policies import TabularQPolicy
from flow_memory.rl.registry import make_env

def test_tabular_q_policy_updates_values() -> None:
    env=make_env("tool_use")
    policy=TabularQPolicy(epsilon=0)
    obs=env.reset()
    policy.update(obs, 0, 1.0, obs, env)
    assert policy.values(obs, env)[0] > 0
    assert TabularQPolicy.from_record(policy.as_record()).q
