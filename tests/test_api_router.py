import unittest

from flow_memory.api.router import create_default_router
from flow_memory.swarm.agent_card import AgentCard


class ApiRouterTests(unittest.TestCase):
    def test_manifest_exposes_registered_endpoints(self) -> None:
        router = create_default_router()

        manifest = router.dispatch("GET", "/manifest")
        endpoints = {(endpoint["method"], endpoint["path"], endpoint["name"]) for endpoint in manifest["endpoints"]}

        self.assertIn(("GET", "/health", "health"), endpoints)
        self.assertIn(("GET", "/agents/{did}", "agents_get"), endpoints)
        self.assertIn(("POST", "/swarm/delegate", "swarm_delegate"), endpoints)
        self.assertIn(("GET", "/verification/{contract_id}", "verification_result"), endpoints)

    def test_agents_and_reputation_endpoints(self) -> None:
        router = create_default_router()
        router.register_agent(
            AgentCard(
                did="did:flow:worker-1",
                name="worker-1",
                capabilities=("vision", "reasoning"),
                reputation=4.5,
            )
        )

        listed = router.dispatch("GET", "/agents")
        fetched = router.dispatch("GET", "/agents/did%3Aflow%3Aworker-1")
        reputation = router.dispatch("GET", "/reputation/did%3Aflow%3Aworker-1")

        self.assertEqual(len(listed["agents"]), 1)
        self.assertEqual(fetched["agent"]["did"], "did:flow:worker-1")
        self.assertEqual(fetched["agent"]["capabilities"], ("vision", "reasoning"))
        self.assertEqual(reputation["score"], 4.5)

    def test_marketplace_task_creation_endpoint(self) -> None:
        router = create_default_router()

        response = router.dispatch(
            "POST",
            "/marketplace/tasks",
            {"title": "label frames", "reward": 2.0, "requester": "did:flow:requester", "metadata": {"n": 3}},
        )

        task = response["task"]
        self.assertTrue(task["task_id"].startswith("task_"))
        self.assertEqual(task["title"], "label frames")
        self.assertEqual(task["reward"], 2.0)
        self.assertEqual(task["status"], "open")
        self.assertEqual(task["metadata"], {"n": 3})

    def test_swarm_delegation_and_verification_endpoints(self) -> None:
        router = create_default_router()
        router.register_agent(
            AgentCard(did="did:flow:worker-2", name="worker-2", capabilities=("summarize",), reputation=0.0)
        )

        delegated = router.dispatch(
            "POST",
            "/swarm/delegate",
            {
                "delegator_did": "did:flow:coordinator",
                "delegate_did": "did:flow:worker-2",
                "capability": "summarize",
                "objective": "summarize local transcript",
                "budget": 1.25,
            },
        )
        contract_id = delegated["delegation"]["contract_id"]
        submitted = router.dispatch(
            "POST",
            f"/verification/{contract_id}",
            {"result": {"summary": "done"}, "accepted": True, "evidence": {"checks": 2}},
        )
        fetched = router.dispatch("GET", f"/verification/{contract_id}")
        reputation = router.dispatch("GET", "/reputation/did%3Aflow%3Aworker-2")

        self.assertEqual(delegated["delegation"]["status"], "assigned")
        self.assertEqual(submitted["verification"]["status"], "verified")
        self.assertEqual(fetched["verification"]["verification"]["evidence"], {"checks": 2})
        self.assertEqual(reputation["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
