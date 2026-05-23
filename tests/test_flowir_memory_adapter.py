import unittest

from flow_memory.ir import MemorySpec
from flow_memory.ir.memory_adapter import memory_config_from_ir


class FlowIRMemoryAdapterTests(unittest.TestCase):
    def test_memory_maps_to_config(self) -> None:
        config = memory_config_from_ir(MemorySpec(working_capacity=9))
        self.assertEqual(config["working_capacity"], 9)


if __name__ == "__main__":
    unittest.main()
