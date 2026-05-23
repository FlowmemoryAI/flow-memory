import unittest

from flow_memory.web3 import UserOperationDraft


class Erc4337AdapterTests(unittest.TestCase):
    def test_user_operation_draft(self) -> None:
        op = UserOperationDraft(sender="0x0", call_data="0x")
        self.assertTrue(op.as_record()["dryRun"])


if __name__ == "__main__":
    unittest.main()
