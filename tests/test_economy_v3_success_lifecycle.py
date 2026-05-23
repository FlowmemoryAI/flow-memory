import unittest

from flow_memory.economy.economy_v3 import EconomyV3


class EconomyV3SuccessTests(unittest.TestCase):
    def test_success_lifecycle_receipts_reputation_memory(self) -> None:
        economy = EconomyV3()
        result = economy.run_success_lifecycle("requester", "worker", "task", 2.0)
        self.assertEqual(result["status"], "settled")
        self.assertGreater(economy.reputation_for("worker").score, 0)
        self.assertTrue(economy.memory_records)
        self.assertTrue(any(receipt.receipt_type == "settlement" for receipt in economy.receipts))


if __name__ == "__main__":
    unittest.main()
