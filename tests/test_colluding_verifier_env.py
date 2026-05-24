from flow_memory.rl.envs.colluding_verifier_env import ColludingVerifierEnv
from flow_memory.rl.policies import HeuristicPolicy


def test_colluding_verifier_env_penalizes_single_false_approval():
    env = ColludingVerifierEnv(seed=13)
    step = env.step(env.action_labels.index("single_verifier_approve"))
    assert step.reward < 0
    assert step.info["metrics"]["collusion_detected"] is True
    assert step.info["metrics"]["false_approval"] is True


def test_colluding_verifier_heuristic_uses_multi_verifier_vote():
    env = ColludingVerifierEnv(seed=13)
    action = HeuristicPolicy().act(env.reset(), env)
    assert env.action_space.label(action) == "multi_verifier_vote"
    step = env.step(action)
    assert step.reward > 0
    assert step.info["metrics"]["success"] is True
