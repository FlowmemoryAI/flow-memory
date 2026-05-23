import unittest

from flow_memory.action.docker_sandbox import DockerSandbox, DockerSandboxConfig, DockerSandboxUnavailable
from flow_memory.action.sandbox_backends import describe_sandbox_backend, select_sandbox_backend
from flow_memory.action.sandbox_policy import evaluate_sandbox_profile
from flow_memory.action.sandbox_profiles import SandboxProfile
from flow_memory.action.sandbox_receipts import SandboxReceipt
from flow_memory.crypto.hashes import content_hash


class SandboxBackendPublicAlphaTests(unittest.TestCase):
    def test_default_backend_is_not_docker_execution(self) -> None:
        selection = describe_sandbox_backend()
        self.assertEqual("container-seam", selection.backend)
        backend = select_sandbox_backend()
        with self.assertRaises(Exception):
            backend.run(("python", "-c", "print('x')"), SandboxProfile())

    def test_unsafe_network_profile_requires_approval(self) -> None:
        decision = evaluate_sandbox_profile(SandboxProfile(network="allow"))
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_approval)

    def test_receipt_includes_metadata(self) -> None:
        profile = SandboxProfile(network="deny")
        receipt = SandboxReceipt(status="planned", profile_hash=content_hash(profile.as_record()), metadata={"backend": "local"})
        self.assertEqual("local", receipt.as_record()["metadata"]["backend"])

    def test_docker_backend_disabled_by_default(self) -> None:
        sandbox = DockerSandbox(DockerSandboxConfig(enabled=False))
        with self.assertRaises(DockerSandboxUnavailable):
            sandbox.run(("python", "-c", "print('x')"), SandboxProfile())


if __name__ == "__main__":
    unittest.main()
