import unittest
from pathlib import Path

from flow_memory.cognition import CognitiveLoop, RuleBasedReasoner
from flow_memory.memory import MemorySystem, WorkingMemory
from flow_memory.perception import DorsalStream, DualStreamPerception, VentralStreamEncoder


class LayoutTests(unittest.TestCase):
    def test_requested_public_modules_exist(self) -> None:
        self.assertIsNotNone(CognitiveLoop)
        self.assertIsNotNone(RuleBasedReasoner)
        self.assertIsNotNone(MemorySystem)
        self.assertIsNotNone(WorkingMemory)
        self.assertIsNotNone(DorsalStream)
        self.assertIsNotNone(DualStreamPerception)
        self.assertIsNotNone(VentralStreamEncoder)

    def test_contract_files_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for rel in ["contracts/AgentRegistry.sol", "contracts/TaskEscrow.sol", "contracts/Reputation.sol", "contracts/Marketplace.sol"]:
            self.assertTrue((root / rel).exists(), rel)


if __name__ == "__main__":
    unittest.main()
