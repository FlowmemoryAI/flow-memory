import unittest

from flow_memory.web3 import chain_by_name


class Web3ChainsTests(unittest.TestCase):
    def test_base_sepolia_chain(self) -> None:
        self.assertEqual(chain_by_name("base-sepolia")["chain_id"], 84532)


if __name__ == "__main__":
    unittest.main()
