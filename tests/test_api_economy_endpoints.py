import unittest

from flow_memory.api.router import create_default_router


class ApiEconomyEndpointTests(unittest.TestCase):
    def test_marketplace_group(self) -> None:
        router = create_default_router()
        task = router.dispatch("POST", "/marketplace/tasks", {"requester": "r", "title": "t", "reward": 1})["task"]
        router.dispatch("POST", "/marketplace/bids", {"task_id": task["task_id"], "agent_did": "a", "price": 1})
        router.dispatch("POST", "/marketplace/assign", {"task_id": task["task_id"], "agent_did": "a"})
        router.dispatch("POST", "/marketplace/submit", {"task_id": task["task_id"], "artifact": {"ok": True}})
        router.dispatch("POST", "/marketplace/verify", {"task_id": task["task_id"], "accepted": True})
        settled = router.dispatch("POST", "/marketplace/settle", {"task_id": task["task_id"]})
        self.assertEqual(settled["settlement"]["status"], "settled")


if __name__ == "__main__":
    unittest.main()
