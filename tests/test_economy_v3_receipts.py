import unittest

from flow_memory.economy.economy_v3 import EconomyV3


class EconomyV3ReceiptTests(unittest.TestCase):
    def test_receipts_are_auditable_and_double_settlement_rejected(self) -> None:
        economy = EconomyV3()
        task = economy.create_task("requester", "task", 1)
        economy.publish_task(task.task_id)
        bid = economy.submit_bid(task.task_id, "worker", 1)
        economy.assign_task(task.task_id, bid.bid_id, "requester")
        economy.create_escrow(task.task_id, "requester")
        economy.submit_work(task.task_id, "worker", {"ok": True})
        economy.verify_work(task.task_id, "requester", True)
        economy.settle(task.task_id, "requester")
        with self.assertRaises(ValueError):
            economy.settle(task.task_id, "requester")
        self.assertEqual(len(economy.audit_log), len(economy.receipts))


if __name__ == "__main__":
    unittest.main()
