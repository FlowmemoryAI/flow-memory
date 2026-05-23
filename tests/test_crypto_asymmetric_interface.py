import unittest

from flow_memory.crypto.asymmetric import LOCAL_TEST_ASYMMETRIC_ALGORITHM, LocalTestSigner
from flow_memory.crypto.did_keys import DidKeyMap
from flow_memory.crypto.ed25519 import Ed25519UnavailableError, ed25519_available, require_ed25519_backend
from flow_memory.crypto.key_registry import KeyRegistry
from flow_memory.crypto.receipt_verifier import verify_receipt_signature
from flow_memory.crypto.signature_policy import public_alpha_policy


class CryptoAsymmetricInterfaceTests(unittest.TestCase):
    def test_local_test_signer_verifies_with_public_record(self) -> None:
        signer = LocalTestSigner(key_id="local-asym", private_seed="deterministic-test-seed")
        payload = {"receipt_id": "r1", "amount": 7, "tags": ["alpha", "rc1"]}

        signature = signer.sign(payload)
        result = signer.verifier().verify(payload, signature)

        self.assertTrue(result.ok)
        self.assertEqual(signature.algorithm, LOCAL_TEST_ASYMMETRIC_ALGORITHM)
        self.assertEqual(signature.public_key, signer.public_record().public_key)

    def test_receipt_verifier_uses_registry_and_policy(self) -> None:
        signer = LocalTestSigner(key_id="receipt-key", private_seed="receipt-seed")
        receipt = {"receipt_id": "r2", "status": "settled"}
        registry = KeyRegistry.from_records([signer.public_record()])

        result = verify_receipt_signature(receipt, signer.sign(receipt), registry, public_alpha_policy())

        self.assertTrue(result.ok)

    def test_receipt_verifier_rejects_unknown_key(self) -> None:
        signer = LocalTestSigner(key_id="missing", private_seed="receipt-seed")
        receipt = {"receipt_id": "r3", "status": "settled"}

        result = verify_receipt_signature(receipt, signer.sign(receipt), KeyRegistry(), public_alpha_policy())

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "unknown key")

    def test_did_key_map_resolves_public_record(self) -> None:
        signer = LocalTestSigner(key_id="did-key", private_seed="did-seed")
        did_keys = DidKeyMap.empty()

        binding = did_keys.bind("did:flow:test-agent", signer.public_record())

        self.assertEqual(binding.key_id, "did-key")
        self.assertEqual(did_keys.key_id_for_did("did:flow:test-agent"), "did-key")
        self.assertEqual(did_keys.public_key_for_did("did:flow:test-agent"), signer.public_record())

    def test_ed25519_adapter_reports_unavailable_without_required_dependency(self) -> None:
        if ed25519_available():
            self.assertIn(require_ed25519_backend(), {"cryptography", "pynacl"})
            return
        with self.assertRaises(Ed25519UnavailableError):
            require_ed25519_backend()


if __name__ == "__main__":
    unittest.main()
