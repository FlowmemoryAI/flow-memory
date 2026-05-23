import unittest

from flow_memory.action.resource_limits import ResourceLimits


class ResourceLimitsTests(unittest.TestCase):
    def test_records_limits(self) -> None:
        self.assertEqual(ResourceLimits(1, 2, 3).as_record()["memory_limit_mb"], 2)


if __name__ == "__main__":
    unittest.main()
