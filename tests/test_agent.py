import unittest

from flow_memory import Agent


class AgentTests(unittest.TestCase):
    def test_first_agent_runs(self) -> None:
        agent = Agent.create(name="alpha", capabilities=["perception", "memory", "reasoning"])
        result = agent.run("Explore the environment and report findings")
        self.assertIn("Processed goal", result)
        self.assertIn("plan approved", result)

    def test_cycle_contains_trace(self) -> None:
        agent = Agent.create(name="alpha")
        cycle = agent.run_cycle("Remember this: safe agents need audit logs")
        self.assertTrue(cycle.action_result.success)
        self.assertTrue(cycle.policy_decision.approved)
        self.assertGreaterEqual(len(cycle.plan.steps), 1)
        self.assertTrue(agent.loop.safety.audit.verify())

    def test_agent_has_did(self) -> None:
        agent = Agent.create(name="alpha")
        self.assertTrue(agent.did.startswith("did:key:"))


if __name__ == "__main__":
    unittest.main()
