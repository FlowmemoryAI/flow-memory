import unittest

from flow_memory.crypto import generate_local_keypair, sign_receipt, verify_receipt


class ReceiptSigningTests(unittest.TestCase):
    def test_receipt_signing(self) -> None:
        key = generate_local_keypair("receipt")
        receipt = {"receipt_id": "r", "status": "settled"}
        signature = sign_receipt(receipt, key)
        self.assertTrue(verify_receipt(receipt, signature, key))


if __name__ == "__main__":
    unittest.main()
