import unittest

from flow_memory.economy import LocalEscrow


class EconomyV2EscrowTests(unittest.TestCase):
    def test_release_and_refund_are_single_use(self) -> None:
        escrow = LocalEscrow()
        account = escrow.fund("task1", payer="requester", payee="agent", amount=3.0)
        released = escrow.release("task1", actor="requester")
        self.assertEqual(released.status, "released")
        with self.assertRaises(ValueError):
            escrow.refund("task1", actor="requester")
        self.assertEqual(account.escrow_id, released.escrow_id)


if __name__ == "__main__":
    unittest.main()
