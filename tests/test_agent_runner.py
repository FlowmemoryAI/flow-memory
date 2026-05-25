import unittest

from flow_memory.agents import create_agent_profile, run_agent_cycle


class AgentRunnerTests(unittest.TestCase):
    def test_safe_agent_cycle_updates_state_memory_and_audit(self) -> None:
        profile = create_agent_profile("runner", allowed_skills=("research-brief",), autonomy_mode="autonomous_local")
        result = run_agent_cycle(profile, "research local topic")
        self.assertTrue(result.accepted)
        self.assertTrue(result.memory_records)
        self.assertTrue(any(event["event"] == "agent_cycle_completed" for event in result.audit_events))

    def test_risky_action_requires_approval(self) -> None:
        profile = create_agent_profile("runner", allowed_skills=("economic-task",), autonomy_mode="supervised")
        result = run_agent_cycle(profile, "settle marketplace task")
        self.assertFalse(result.accepted)
        self.assertTrue(result.requires_approval)

    def test_economic_action_respects_risk_budget(self) -> None:
        profile = create_agent_profile("econ", identity="did:flow:econ", allowed_skills=("economic-task",), autonomy_mode="autonomous_economic", max_spend=2)
        result = run_agent_cycle(profile, "settle marketplace task")
        self.assertTrue(result.accepted)
        self.assertEqual(result.output["settlement"]["status"], "settled")


if __name__ == "__main__":
    unittest.main()
