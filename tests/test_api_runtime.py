import unittest

from flow_memory.api import create_default_router


class ApiRuntimeTests(unittest.TestCase):
    def test_runtime_tick_updates_status(self) -> None:
        router = create_default_router()
        self.assertEqual(router.dispatch("GET", "/runtime/status")["ticks"], 0)
        router.dispatch("POST", "/runtime/tick")
        self.assertEqual(router.dispatch("GET", "/runtime/status")["ticks"], 1)


if __name__ == "__main__":
    unittest.main()
