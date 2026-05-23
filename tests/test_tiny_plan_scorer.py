from flow_memory.agents.planner import CognitivePlanner
from flow_memory.neural.agent.plan_scorer import TinyPlanScorer


def test_tiny_plan_scorer_scores_candidate_plan():
    plan = CognitivePlanner().create_plan("write local summary")
    score = TinyPlanScorer().score_plan(plan)
    assert score.total_score > 0
