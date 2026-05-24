from flow_memory.rl.policies import HeuristicPolicy
from flow_memory.rl.registry import make_env

def test_heuristic_policy_uses_safe_action():
    env=make_env("safety_gate")
    action=HeuristicPolicy().act(env.reset(), env)
    assert env.action_space.label(action) == "choose_safer_plan"
