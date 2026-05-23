import unittest

from flow_memory.api.router import create_default_router
from flow_memory.flowlang.examples import EXAMPLE_FLOWLANG


class FlowLangApiTests(unittest.TestCase):
    def test_flowlang_endpoints_work(self) -> None:
        router = create_default_router()
        compiled = router.dispatch("POST", "/flowlang/compile", {"source": EXAMPLE_FLOWLANG})
        validated = router.dispatch("POST", "/flowlang/validate", {"source": EXAMPLE_FLOWLANG})
        run = router.dispatch("POST", "/flowlang/run", {"source": EXAMPLE_FLOWLANG, "prompt": "Run the declared agent"})
        self.assertTrue(compiled["ok"])
        self.assertEqual(validated["errors"], ())
        self.assertIn("accepted", run)


if __name__ == "__main__":
    unittest.main()
