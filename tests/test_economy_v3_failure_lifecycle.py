import unittest

from flow_memory.economy.economy_v3 import EconomyV3


class EconomyV3FailureTests(unittest.TestCase):
    def test_failure_lifecycle_dispute_slashes(self) -> None:
        economy = EconomyV3()
        result = economy.run_failure_lifecycle("requester", "worker", "task", 2.0)
        self.assertEqual(result["status"], "slashed")
        self.assertLess(economy.reputation_for("worker").score, 0)
        self.assertTrue(any(receipt.receipt_type == "slashing" for receipt in economy.receipts))


if __name__ == "__main__":
    unittest.main()
