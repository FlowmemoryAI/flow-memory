import unittest

from flow_memory.action.sandbox_policy import sandbox_requires_approval
from flow_memory.action.sandbox_profiles import SandboxProfile


class SandboxPolicyTests(unittest.TestCase):
    def test_unsafe_profiles_require_approval(self) -> None:
        self.assertTrue(sandbox_requires_approval(SandboxProfile(network="allow")))
        self.assertFalse(sandbox_requires_approval(SandboxProfile()))


if __name__ == "__main__":
    unittest.main()
