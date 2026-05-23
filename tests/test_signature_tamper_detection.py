import unittest

from flow_memory.crypto import generate_local_keypair, sign_payload, verify_payload
from flow_memory.crypto.asymmetric import LocalTestSigner
from flow_memory.crypto.key_registry import KeyRegistry
from flow_memory.crypto.receipt_verifier import verify_receipt_signature
from flow_memory.crypto.signature_policy import public_alpha_policy


class SignatureTamperDetectionTests(unittest.TestCase):
    def test_dev_hmac_rejects_payload_tampering(self) -> None:
        key = generate_local_keypair("dev")
        payload = {"receipt_id": "r1", "status": "settled"}
        signature = sign_payload(payload, key)

        tampered = {"receipt_id": "r1", "status": "refunded"}

        self.assertFalse(verify_payload(tampered, signature, key))

    def test_asymmetric_receipt_verifier_rejects_payload_tampering(self) -> None:
        signer = LocalTestSigner(key_id="asym", private_seed="seed")
        receipt = {"receipt_id": "r2", "status": "settled", "amount": 42}
        signature = signer.sign(receipt)
        tampered = {"receipt_id": "r2", "status": "settled", "amount": 43}
        registry = KeyRegistry.from_records([signer.public_record()])

        result = verify_receipt_signature(tampered, signature, registry, public_alpha_policy())

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "payload hash mismatch")

    def test_asymmetric_receipt_verifier_rejects_signature_tampering(self) -> None:
        signer = LocalTestSigner(key_id="asym", private_seed="seed")
        receipt = {"receipt_id": "r3", "status": "settled"}
        signature = signer.sign(receipt)
        tampered_signature = {**signature.as_record(), "signature": "0" * len(signature.signature)}
        registry = KeyRegistry.from_records([signer.public_record()])

        result = verify_receipt_signature(receipt, tampered_signature, registry, public_alpha_policy())

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "signature mismatch")

    def test_public_alpha_policy_rejects_dev_hmac_receipts(self) -> None:
        key = generate_local_keypair("dev")
        receipt = {"receipt_id": "r4", "status": "settled"}
        signature = sign_payload(receipt, key)

        result = verify_receipt_signature(receipt, signature, KeyRegistry(), public_alpha_policy())

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "dev_hmac is local/demo only")


if __name__ == "__main__":
    unittest.main()
