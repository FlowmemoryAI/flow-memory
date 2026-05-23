import unittest

from flow_memory.skills import SkillEvaluator
from flow_memory.skills.runner import SkillRunResult


class SkillEvaluatorTests(unittest.TestCase):
    def test_scores_successful_structured_output(self) -> None:
        evaluation = SkillEvaluator().evaluate(SkillRunResult("brief", True, output={"brief": "a useful local research brief"}))
        self.assertGreaterEqual(evaluation.score, 4.0)
        self.assertTrue(evaluation.passed)

    def test_failed_skill_scores_low(self) -> None:
        evaluation = SkillEvaluator().evaluate(SkillRunResult("brief", False, error="api rate limited"))
        self.assertEqual(evaluation.score, 1.0)
        self.assertIn("rate_limited", evaluation.flags)


if __name__ == "__main__":
    unittest.main()
