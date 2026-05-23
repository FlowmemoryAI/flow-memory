import unittest

from flow_memory.agents import CognitivePlanner


class AgentPlannerTests(unittest.TestCase):
    def test_planner_creates_typed_safe_and_economic_plans(self) -> None:
        planner = CognitivePlanner()
        safe = planner.create_plan("research", allowed_skills=("research-brief",))
        economic = planner.create_plan("settle marketplace task", allowed_skills=("economic-task",))
        self.assertEqual(safe.steps[0].required_skills, ("research-brief",))
        self.assertEqual(economic.risk_level, "high")
        self.assertTrue(economic.economic_intent)


if __name__ == "__main__":
    unittest.main()
