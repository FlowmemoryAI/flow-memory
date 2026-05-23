import unittest

from flow_memory.api import endpoint_manifest


class ApiManifestTests(unittest.TestCase):
    def test_manifest_contains_required_endpoint_groups(self) -> None:
        paths = {endpoint["path"] for endpoint in endpoint_manifest()["endpoints"]}
        self.assertIn("/health", paths)
        self.assertIn("/runtime/status", paths)
        self.assertIn("/marketplace/tasks", paths)
        self.assertIn("/swarm/delegate", paths)
        self.assertIn("/verification/submit", paths)


if __name__ == "__main__":
    unittest.main()
