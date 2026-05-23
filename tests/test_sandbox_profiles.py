import unittest

from flow_memory.action.sandbox_profiles import SandboxProfile


class SandboxProfileTests(unittest.TestCase):
    def test_profile_validation(self) -> None:
        self.assertEqual(SandboxProfile().validate(), ())
        self.assertTrue(SandboxProfile(network="allow").as_record()["network"])


if __name__ == "__main__":
    unittest.main()
