import unittest

from flow_memory.economy.economy_v3 import EconomicRiskControls, EconomyV3


class EconomyV3RiskTests(unittest.TestCase):
    def test_risk_budget_blocks_excessive_bid(self) -> None:
        economy = EconomyV3(EconomicRiskControls(max_spend_per_agent=1, max_escrow_exposure=1))
        task = economy.create_task("requester", "expensive", 5)
        economy.publish_task(task.task_id)
        with self.assertRaises(PermissionError):
            economy.submit_bid(task.task_id, "worker", 5)


if __name__ == "__main__":
    unittest.main()
