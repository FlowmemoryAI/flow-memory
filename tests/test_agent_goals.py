import unittest

from flow_memory.agents import Goal, GoalPriority, GoalStack


class AgentGoalsTests(unittest.TestCase):
    def test_goal_stack_prioritizes_and_detects_conflicts(self) -> None:
        stack = GoalStack()
        stack.push(Goal("write memory", priority=GoalPriority.LOW))
        stack.push(Goal("urgent", priority=GoalPriority.CRITICAL))
        stack.push(Goal("do not write memory"))
        active = stack.active()
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.description, "urgent")
        self.assertTrue(stack.conflicts())


if __name__ == "__main__":
    unittest.main()
