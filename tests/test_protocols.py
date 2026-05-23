import unittest

from flow_memory.action.tools import default_tool_registry
from flow_memory.protocols import (
    AgentMessage,
    CapabilityManifest,
    LocalA2ABus,
    registry_to_mcp_manifest,
    tool_to_mcp_spec,
)


class ProtocolTests(unittest.TestCase):
    def test_mcp_spec_from_tool(self) -> None:
        tool = default_tool_registry().get("echo")
        spec = tool_to_mcp_spec(tool)
        self.assertEqual(spec.name, "echo")
        self.assertEqual(spec.required_permission, "respond")

    def test_registry_manifest(self) -> None:
        manifest = registry_to_mcp_manifest(default_tool_registry())
        self.assertEqual(manifest["protocol"], "mcp-compatible")
        self.assertGreaterEqual(len(manifest["tools"]), 2)

    def test_local_a2a_bus(self) -> None:
        bus = LocalA2ABus()
        bus.send(AgentMessage(sender_did="did:key:a", recipient_did="did:key:b", kind="ping", payload={}))
        messages = bus.receive("did:key:b")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].kind, "ping")

    def test_discovery_by_capability(self) -> None:
        bus = LocalA2ABus()
        manifest = CapabilityManifest("did:key:a", "alpha", ["memory"], ["respond"])
        bus.register("did:key:a", manifest)
        self.assertEqual(bus.discover("memory"), (manifest,))


if __name__ == "__main__":
    unittest.main()
