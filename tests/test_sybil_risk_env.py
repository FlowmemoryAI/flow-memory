from flow_memory.rl.envs.sybil_risk_env import SybilRiskEnv
from flow_memory.rl.policies import HeuristicPolicy


def test_sybil_risk_env_flags_duplicate_signal() -> None:
    env = SybilRiskEnv(seed=11)
    step = env.step(env.action_labels.index("ignore_duplicate_signal"))
    assert step.reward < 0
    assert step.info["metrics"]["sybil_risk_flagged"] is True
    assert step.observation["safety"]["violations"] == 1


def test_sybil_risk_heuristic_quarantines_cluster() -> None:
    env = SybilRiskEnv(seed=11)
    action = HeuristicPolicy().act(env.reset(), env)
    assert env.action_space.label(action) == "quarantine_cluster"
    step = env.step(action)
    assert step.reward > 0
    assert step.info["metrics"]["success"] is True
