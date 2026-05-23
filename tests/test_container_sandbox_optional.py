import unittest

from flow_memory.action.container_sandbox import ContainerSandbox, ContainerSandboxUnavailable
from flow_memory.action.sandbox_profiles import SandboxProfile


class ContainerSandboxOptionalTests(unittest.TestCase):
    def test_container_sandbox_unavailable_by_default(self) -> None:
        with self.assertRaises(ContainerSandboxUnavailable):
            ContainerSandbox().run(("echo", "hi"), SandboxProfile())


if __name__ == "__main__":
    unittest.main()
