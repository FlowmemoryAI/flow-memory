import unittest

from flow_memory.ir import AgentSpec, envelope_manifest, sign_manifest, verify_manifest_signature


class FlowIRManifestSecurityTests(unittest.TestCase):
    def test_envelope_and_signature(self) -> None:
        agent = AgentSpec(name="secure")
        envelope = envelope_manifest(agent)
        signed = sign_manifest(agent, "secret")
        self.assertEqual(envelope.schema_version, "flowir/v0.1")
        self.assertTrue(verify_manifest_signature(signed, "secret"))
        tampered = signed.as_record()
        tampered["envelope"]["manifest"]["name"] = "other"
        self.assertFalse(verify_manifest_signature(tampered, "secret"))


if __name__ == "__main__":
    unittest.main()
