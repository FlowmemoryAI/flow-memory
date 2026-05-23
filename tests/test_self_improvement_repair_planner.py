import unittest

from flow_memory.self_improvement import HealthMonitor, RepairPlanner


class SelfImprovementRepairPlannerTests(unittest.TestCase):
    def test_unsafe_repair_requires_approval_and_does_not_apply_code(self) -> None:
        report = HealthMonitor().assess(unsafe_actions=1)
        plan = RepairPlanner().plan(report)
        self.assertTrue(plan.requires_approval)
        self.assertFalse(plan.applies_code)
        self.assertEqual(plan.steps[0].flag, "unsafe_action")


if __name__ == "__main__":
    unittest.main()
