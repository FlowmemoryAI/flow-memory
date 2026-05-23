import unittest

from flow_memory.crypto import generate_local_keypair, sign_manifest, verify_manifest


class ManifestSigningTests(unittest.TestCase):
    def test_manifest_signing_and_tamper_detection(self) -> None:
        key = generate_local_keypair("manifest")
        manifest = {"name": "agent"}
        signature = sign_manifest(manifest, key)
        self.assertTrue(verify_manifest(manifest, signature, key))
        self.assertFalse(verify_manifest({"name": "other"}, signature, key))


if __name__ == "__main__":
    unittest.main()
