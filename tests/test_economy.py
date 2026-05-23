import unittest

from flow_memory.core.types import ActionResult, Plan, PlanStep
from flow_memory.economy.layer import EconomicLayer
from flow_memory.economy.wallet import SmartWallet


class EconomyTests(unittest.TestCase):
    def test_economic_settlement_credits_wallet(self) -> None:
        economy = EconomicLayer()
        plan = Plan(goal="complete task", steps=(PlanStep(action="respond", economic_value=2.5),))
        result = ActionResult(success=True, output="done")
        settlement = economy.settle(plan, result)
        self.assertTrue(settlement["settled"])
        self.assertEqual(economy.wallet.balance, 2.5)
        self.assertGreater(economy.reputation.score, 0)

    def test_marketplace_lifecycle(self) -> None:
        economy = EconomicLayer()
        task_id = economy.marketplace.post_task("test task", reward=1.0, requester="requester")
        bid_id = economy.marketplace.bid(task_id, economy.identity.uri(), price=1.0)
        economy.marketplace.accept_bid(task_id, bid_id)
        settled = economy.marketplace.settle(task_id, success=True)
        self.assertTrue(bid_id.startswith("bid_"))
        self.assertEqual(settled["status"], "settled_success")
        self.assertEqual(settled["assigned_bid"], bid_id)
        self.assertEqual(settled["assignee"], economy.identity.uri())
        self.assertEqual(settled["reward"], 1.0)
        self.assertEqual(settled["bid_price"], 1.0)

    def test_marketplace_assigns_lowest_bid(self) -> None:
        economy = EconomicLayer()
        task_id = economy.marketplace.post_task("test task", reward=2.0, requester="requester")
        high_bid = economy.marketplace.bid(task_id, "did:key:high", price=1.5)
        low_bid = economy.marketplace.bid(task_id, "did:key:low", price=0.75)

        assigned = economy.marketplace.assign_lowest_bid(task_id)
        settled = economy.marketplace.settle(task_id, success=True)

        self.assertEqual(assigned.status, "assigned")
        self.assertNotEqual(high_bid, low_bid)
        self.assertEqual(settled["assigned_bid"], low_bid)
        self.assertEqual(settled["assignee"], "did:key:low")

    def test_marketplace_rejects_unassigned_settlement(self) -> None:
        economy = EconomicLayer()
        task_id = economy.marketplace.post_task("test task", reward=1.0, requester="requester")
        economy.marketplace.bid(task_id, economy.identity.uri(), price=1.0)

        with self.assertRaisesRegex(ValueError, "not assigned"):
            economy.marketplace.settle(task_id, success=True)

    def test_marketplace_rejects_double_settlement(self) -> None:
        economy = EconomicLayer()
        task_id = economy.marketplace.post_task("test task", reward=1.0, requester="requester")
        bid_id = economy.marketplace.bid(task_id, economy.identity.uri(), price=1.0)
        economy.marketplace.accept_bid(task_id, bid_id)

        economy.marketplace.settle(task_id, success=True)

        with self.assertRaisesRegex(ValueError, "already settled"):
            economy.marketplace.settle(task_id, success=True)

    def test_marketplace_success_records_reputation_and_credit(self) -> None:
        economy = EconomicLayer()
        task_id = economy.marketplace.post_task("test task", reward=1.5, requester="requester")
        bid_id = economy.marketplace.bid(task_id, economy.identity.uri(), price=1.25)
        economy.marketplace.accept_bid(task_id, bid_id)

        settled = economy.settle_marketplace_task(task_id, success=True)

        self.assertEqual(settled["status"], "settled_success")
        self.assertEqual(settled["economic_status"], "credited")
        self.assertEqual(economy.wallet.balance, 1.5)
        self.assertEqual(economy.reputation.score, 1.0)
        self.assertEqual(economy.reputation.events[-1]["task_id"], task_id)
        self.assertEqual(economy.reputation.events[-1]["delta"], 1.0)

    def test_marketplace_failure_records_reputation_slash(self) -> None:
        economy = EconomicLayer()
        task_id = economy.marketplace.post_task("test task", reward=1.5, requester="requester")
        bid_id = economy.marketplace.bid(task_id, economy.identity.uri(), price=1.25)
        economy.marketplace.accept_bid(task_id, bid_id)

        settled = economy.settle_marketplace_task(task_id, success=False)

        self.assertEqual(settled["status"], "settled_failure")
        self.assertEqual(settled["economic_status"], "slashed_reputation")
        self.assertEqual(economy.wallet.balance, 0.0)
        self.assertEqual(economy.reputation.score, -1.0)
        self.assertEqual(economy.reputation.events[-1]["task_id"], task_id)
        self.assertEqual(economy.reputation.events[-1]["delta"], -1.0)

    def test_wallet_queues_user_operation(self) -> None:
        wallet = SmartWallet()
        op = wallet.queue_operation("0x" + "1" * 40, value=0, data={"call": "noop"})
        self.assertTrue(op.operation_id.startswith("userop_"))


if __name__ == "__main__":
    unittest.main()
