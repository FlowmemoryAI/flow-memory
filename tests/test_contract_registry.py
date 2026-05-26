import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flow_memory.web3.contract_registry import CONTRACTS, ZERO_ADDRESS, ContractRegistry, is_address, write_registry
from typing import Any, Mapping, cast


class ContractRegistryTests(unittest.TestCase):
    def test_registry_records_addresses(self) -> None:
        registry = ContractRegistry()
        registry.register("AgentRegistry", ZERO_ADDRESS)
        self.assertIn("AgentRegistry", cast(Mapping[str, Any], registry.as_record()["addresses"]))

    def test_rejects_invalid_address_and_unknown_contract(self) -> None:
        registry = ContractRegistry()
        with self.assertRaises(ValueError):
            registry.register("AgentRegistry", "not-an-address")
        with self.assertRaises(ValueError):
            registry.register("Unknown", ZERO_ADDRESS)
        self.assertTrue(is_address(ZERO_ADDRESS))

    def test_validation_reports_missing_and_zero_addresses(self) -> None:
        registry = ContractRegistry()
        registry.register("AgentRegistry", ZERO_ADDRESS)
        validation = registry.validate()

        self.assertFalse(validation.ok)
        self.assertIn("TaskMarketplace", validation.missing_contracts)
        self.assertIn("AgentRegistry", validation.zero_addresses)

    def test_verify_contract_config_script_accepts_complete_dry_run_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[1]
            registry = ContractRegistry()
            for index, name in enumerate(CONTRACTS, start=1):
                registry.register(name, "0x" + f"{index:040x}")
            registry_path = Path(tmp) / "registry.json"
            write_registry(registry, registry_path)

            completed = subprocess.run(
                [sys.executable, "scripts/verify_contract_config.py", "--registry", str(registry_path)],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
