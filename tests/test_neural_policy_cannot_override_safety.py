from flow_memory.agents.autonomy import decide_autonomy
from flow_memory.neural.agent.risk_model import TinyRiskModel


def test_neural_scores_do_not_override_policy_authority() -> None:
    neural = TinyRiskModel().score("unsafe wallet transfer")
    decision = decide_autonomy("supervised", risk_level="high", economic_value=1.0, max_spend=100.0)
    assert neural.approval_required_likelihood > 0
    assert decision.allowed is False
    assert decision.requires_approval is True
