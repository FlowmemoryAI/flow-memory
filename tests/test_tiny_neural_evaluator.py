from flow_memory.neural.agent.evaluator import TinyNeuralEvaluator


def test_tiny_neural_evaluator_total_score() -> None:
    result = TinyNeuralEvaluator().evaluate({"ok": True}, memory_hits=2, economic_value=1.0)
    assert 0 <= result.total_score <= 1
