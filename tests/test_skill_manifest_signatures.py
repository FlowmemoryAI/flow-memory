import unittest

from flow_memory.crypto import generate_local_keypair, sign_payload, verify_payload
from flow_memory.skills import SkillManifest


class SkillManifestSignatureTests(unittest.TestCase):
    def test_skill_manifest_signature(self) -> None:
        manifest = SkillManifest(id="s", name="Skill", description="desc")
        key = generate_local_keypair("skill")
        signature = sign_payload(manifest.as_record(), key)
        self.assertTrue(verify_payload(manifest.as_record(), signature, key))


if __name__ == "__main__":
    unittest.main()
