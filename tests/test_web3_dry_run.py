import unittest

from flow_memory.web3 import base_sepolia_dry_run, build_dry_run_transaction


class Web3DryRunTests(unittest.TestCase):
    def test_dry_run_transaction_payload(self) -> None:
        tx = build_dry_run_transaction("0x0000000000000000000000000000000000000000")
        self.assertTrue(tx["dry_run"])
        self.assertIn("plan", base_sepolia_dry_run())


if __name__ == "__main__":
    unittest.main()
