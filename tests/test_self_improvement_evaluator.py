import unittest

from flow_memory.self_improvement.evaluator import SelfEvaluator


class SelfImprovementEvaluatorTests(unittest.TestCase):
    def test_scores_structured_output(self) -> None:
        score = SelfEvaluator().score("skill", {"result": "a long enough useful result"}, expected_fields=("result",))
        self.assertGreaterEqual(score.score, 4.0)

    def test_missing_expected_field_sets_flag(self) -> None:
        score = SelfEvaluator().score("skill", {"other": "value"}, expected_fields=("result",))
        self.assertIn("missing_fields", score.flags)


if __name__ == "__main__":
    unittest.main()
