import unittest
from pathlib import Path

from flow_memory.flowlang import run_flowlang_agent


class FlowLangEconomyLifecycleTests(unittest.TestCase):
    def test_flowlang_economic_plan_settles_locally(self) -> None:
        result = run_flowlang_agent(Path("examples/flowlang_economy_agent.flow"), "settle marketplace task")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["output"]["settlement"]["status"], "settled")


if __name__ == "__main__":
    unittest.main()
