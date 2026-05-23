import unittest

from flow_memory.agents import AgentEvaluation, AgentReflector


class AgentReflectionTests(unittest.TestCase):
    def test_reflection_recommends_repair_for_failure(self) -> None:
        report = AgentReflector().reflect(AgentEvaluation(quality_score=0.1, surprise_score=1.0, success=False))
        self.assertTrue(report.consolidate_memory)
        self.assertIn("repair", report.repair_recommendation)


if __name__ == "__main__":
    unittest.main()
