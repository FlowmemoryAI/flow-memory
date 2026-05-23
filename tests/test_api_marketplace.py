import unittest

from flow_memory.api import create_default_router


class ApiMarketplaceTests(unittest.TestCase):
    def test_create_bid_and_settle_task(self) -> None:
        router = create_default_router()
        task = router.dispatch("POST", "/marketplace/tasks", {"title": "work", "requester": "did:r", "reward": 2})["task"]
        bid = router.dispatch("POST", "/marketplace/bids", {"task_id": task["task_id"], "agent_did": "did:a", "price": 1})["bid"]
        settlement = router.dispatch("POST", "/marketplace/settle", {"task_id": task["task_id"]})["settlement"]
        self.assertEqual(bid["task_id"], task["task_id"])
        self.assertEqual(settlement["status"], "settled")


if __name__ == "__main__":
    unittest.main()
