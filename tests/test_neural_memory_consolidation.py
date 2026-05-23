from flow_memory.neural.memory.consolidation_model import TinyConsolidationModel


def test_safety_and_economy_prioritized_for_consolidation():
    score = TinyConsolidationModel().score("blocked policy settlement dispute", surprise=0.5)
    assert score.priority > 0.4
