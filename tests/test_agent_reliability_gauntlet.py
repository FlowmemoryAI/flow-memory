import json
import unittest

from flow_memory.agents.gauntlet import run_offline_reliability_gauntlet


class AgentReliabilityGauntletTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = run_offline_reliability_gauntlet()
        self.reports = {report["scenario_name"]: report for report in self.result["reports"]}

    def test_runs_required_named_scenarios(self) -> None:
        expected = {
            "SafeLocalSkillScenario",
            "RiskyActionBlockedScenario",
            "ManualApprovalRequiredScenario",
            "FlowLangAgentRuntimeScenario",
            "MemoryWritePolicyScenario",
            "SkillFailureRecoveryScenario",
            "EconomySuccessScenario",
            "EconomyFailureDisputeScenario",
            "SwarmDelegationScenario",
            "ReputationRoutingScenario",
            "BudgetExceededBlockedScenario",
            "RepeatedFailureCooldownScenario",
        }
        self.assertEqual(self.result["scenario_count"], 12)
        self.assertEqual(set(self.reports), expected)
        json.dumps(self.result)

    def test_blocked_scenarios_capture_policy_decisions(self) -> None:
        risky = self.reports["RiskyActionBlockedScenario"]
        manual = self.reports["ManualApprovalRequiredScenario"]
        budget = self.reports["BudgetExceededBlockedScenario"]
        cooldown = self.reports["RepeatedFailureCooldownScenario"]

        self.assertTrue(risky["passed"])
        self.assertFalse(risky["policy_decisions"][0]["allowed"])
        self.assertTrue(risky["policy_decisions"][0]["requires_approval"])
        self.assertEqual(risky["failures"][0]["kind"], "blocked")

        self.assertTrue(manual["passed"])
        self.assertTrue(manual["policy_decisions"][0]["requires_approval"])

        self.assertTrue(budget["passed"])
        self.assertIn("budget", budget["failures"][0]["kind"])
        self.assertTrue(budget["policy_decisions"][0]["requires_approval"])

        self.assertTrue(cooldown["passed"])
        self.assertEqual(cooldown["recovery_actions"][0]["action"], "cooldown_started")
        self.assertTrue(cooldown["recovery_actions"][0]["blocked_next_attempt"])

    def test_recovery_and_economy_outcomes_are_recorded(self) -> None:
        recovery = self.reports["SkillFailureRecoveryScenario"]
        economy_success = self.reports["EconomySuccessScenario"]
        economy_failure = self.reports["EconomyFailureDisputeScenario"]

        self.assertTrue(recovery["passed"])
        self.assertEqual(recovery["failures"][0]["kind"], "skill_failure")
        self.assertEqual(recovery["recovery_actions"][0]["action"], "fallback_skill")
        self.assertTrue(recovery["recovery_actions"][0]["success"])

        self.assertTrue(economy_success["passed"])
        self.assertIn("settlement", {receipt["receipt_type"] for receipt in economy_success["economy_receipts"]})

        self.assertTrue(economy_failure["passed"])
        receipt_types = {receipt["receipt_type"] for receipt in economy_failure["economy_receipts"]}
        self.assertIn("dispute", receipt_types)
        self.assertIn("dispute_resolved", receipt_types)


if __name__ == "__main__":
    unittest.main()
