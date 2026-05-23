from flow_memory.neural.agent.risk_model import TinyRiskModel


def test_tiny_risk_model_flags_unsafe_economic_text():
    score = TinyRiskModel().score("wallet transfer marketplace settlement")
    assert score.approval_required_likelihood > 0
