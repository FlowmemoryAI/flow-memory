from flow_memory.rl.envs.reputation_gaming_env import ReputationGamingEnv
from flow_memory.rl.policies import HeuristicPolicy


def test_reputation_gaming_env_penalizes_wash_trading():
    env = ReputationGamingEnv(seed=7)
    step = env.step(env.action_labels.index("wash_trade"))
    assert step.reward < 0
    assert step.info["metrics"]["reputation_gaming_detected"] is True
    assert step.observation["economy"]["slashing_events"] == 1


def test_reputation_gaming_heuristic_declines_suspicious_task():
    env = ReputationGamingEnv(seed=7)
    action = HeuristicPolicy().act(env.reset(), env)
    assert env.action_space.label(action) == "decline_suspicious_task"
    step = env.step(action)
    assert step.reward > 0
    assert step.info["metrics"]["safety_violation"] is False
