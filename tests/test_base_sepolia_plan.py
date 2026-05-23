import unittest

from flow_memory.web3 import generate_deployment_plan


class BaseSepoliaPlanTests(unittest.TestCase):
    def test_plan_is_dry_run(self) -> None:
        plan = generate_deployment_plan()
        self.assertEqual(plan["mode"], "dry-run")
        self.assertFalse(plan["requires_private_key"])


if __name__ == "__main__":
    unittest.main()
