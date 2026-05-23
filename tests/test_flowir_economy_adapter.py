import unittest

from flow_memory.ir import EconomicSpec
from flow_memory.ir.economy_adapter import economy_config_from_ir


class FlowIREconomyAdapterTests(unittest.TestCase):
    def test_economy_maps_to_config(self) -> None:
        config = economy_config_from_ir(EconomicSpec(settlement="local", budget=2))
        self.assertEqual(config["settlement"], "local")
        self.assertEqual(config["budget"], 2.0)


if __name__ == "__main__":
    unittest.main()
