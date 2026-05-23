import unittest

from flow_memory.agents import create_agent_profile, run_agent_cycle


class EconomyV3AgentIntegrationTests(unittest.TestCase):
    def test_agent_economic_action_runs_through_risk_budget(self) -> None:
        profile = create_agent_profile("econ", identity="did:flow:econ", allowed_skills=("economic-task",), autonomy_mode="autonomous_economic", max_spend=2)
        result = run_agent_cycle(profile, "settle marketplace task")
        self.assertTrue(result.accepted)
        self.assertEqual(result.output["settlement"]["status"], "settled")


if __name__ == "__main__":
    unittest.main()
