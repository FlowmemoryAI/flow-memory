from flow_memory.rl.evaluator import RLEvaluator
from flow_memory.rl.policies import HeuristicPolicy
from flow_memory.rl.registry import make_env


def test_rl_evaluator_reports_metrics():
    report = RLEvaluator().evaluate(make_env("tool_use"), HeuristicPolicy(), episodes=3)
    assert report["mean_reward"] > 0
    assert report["mean_success_rate"] == 1.0
