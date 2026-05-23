import unittest

from flow_memory.action.sandbox_receipts import SandboxReceipt


class SandboxReceiptTests(unittest.TestCase):
    def test_receipt_record(self) -> None:
        self.assertEqual(SandboxReceipt("ok", "hash", 2).as_record()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
