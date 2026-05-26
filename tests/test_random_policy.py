from flow_memory.rl.policies import RandomPolicy
from flow_memory.rl.registry import make_env

def test_random_policy_selects_valid_action() -> None:
    env=make_env("gridworld")
    action=RandomPolicy(seed=1).act(env.reset(), env)
    assert env.action_space.contains(action)
