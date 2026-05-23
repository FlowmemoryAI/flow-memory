import unittest

from flow_memory.agents import AgentProfile, RiskBudget


class AgentProfileTests(unittest.TestCase):
    def test_profile_validates_and_records_fields(self) -> None:
        profile = AgentProfile(name="alpha", identity="did:flow:alpha", risk_budget=RiskBudget(max_spend=2))
        self.assertEqual(profile.validate(), ())
        self.assertEqual(profile.as_record()["identity"], "did:flow:alpha")


if __name__ == "__main__":
    unittest.main()
