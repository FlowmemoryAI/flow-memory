import pytest


def test_tiny_agent_policy_network_scores() -> None:
    torch = pytest.importorskip("torch")
    from flow_memory.neural.agent.policy import TinyAgentPolicyNetwork

    x = torch.ones(4)
    score = TinyAgentPolicyNetwork().score(x, x, x, x)
    assert 0.0 <= score.plan_ranking_score <= 1.0
