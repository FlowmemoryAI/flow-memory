import unittest

from flow_memory.web3.bundler import BundlerAdapter, BundlerNotConfigured
from flow_memory.web3.paymaster import PaymasterAdapter, PaymasterNotConfigured


class BundlerPaymasterTests(unittest.TestCase):
    def test_adapters_fail_clearly_when_unconfigured(self) -> None:
        with self.assertRaises(BundlerNotConfigured):
            BundlerAdapter().send_user_operation({})
        with self.assertRaises(PaymasterNotConfigured):
            PaymasterAdapter().sponsor_user_operation({})


if __name__ == "__main__":
    unittest.main()
