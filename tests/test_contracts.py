import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_contract_scaffolds_exist(self) -> None:
        for name in ["AgentRegistry.sol", "TaskEscrow.sol", "Reputation.sol", "TaskMarketplace.sol"]:
            path = ROOT / "contracts" / name
            self.assertTrue(path.exists(), name)
            text = path.read_text(encoding="utf-8")
            self.assertIn("SPDX-License-Identifier: Apache-2.0", text)
            self.assertIn("pragma solidity", text)

    def test_registry_and_reputation_are_not_recursive_aliases(self) -> None:
        registry = (ROOT / "contracts" / "AgentRegistry.sol").read_text(encoding="utf-8")
        reputation = (ROOT / "contracts" / "Reputation.sol").read_text(encoding="utf-8")
        self.assertNotIn('import "./AgentRegistry.sol"', registry)
        self.assertNotIn('import "./Reputation.sol"', reputation)
        self.assertIn("function registerAgent", registry)
        self.assertIn("function applyDelta", reputation)
        self.assertIn("non-transferable", reputation.lower())


if __name__ == "__main__":
    unittest.main()
