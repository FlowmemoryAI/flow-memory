import unittest

from flow_memory.web3.contract_registry import ContractRegistry


class ContractRegistryTests(unittest.TestCase):
    def test_registry_records_addresses(self) -> None:
        registry = ContractRegistry()
        registry.register("AgentRegistry", "0x0000000000000000000000000000000000000000")
        self.assertIn("AgentRegistry", registry.as_record()["addresses"])


if __name__ == "__main__":
    unittest.main()
