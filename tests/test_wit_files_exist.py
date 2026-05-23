import unittest
from pathlib import Path


class WitFilesExistTests(unittest.TestCase):
    def test_required_wit_files_exist_and_define_worlds(self) -> None:
        root = Path(__file__).resolve().parents[1]
        files = {
            "flow-memory-skill.wit": "world flow-memory-skill",
            "flow-memory-agent.wit": "world flow-memory-agent",
            "flow-memory-memory.wit": "world flow-memory-memory",
            "flow-memory-economy.wit": "world flow-memory-economy",
        }
        for filename, expected in files.items():
            content = (root / "wit" / filename).read_text(encoding="utf-8")
            self.assertIn(expected, content)
            self.assertIn("package flow-memory:", content)

    def test_skill_wit_contains_required_abi_terms(self) -> None:
        root = Path(__file__).resolve().parents[1]
        content = (root / "wit" / "flow-memory-skill.wit").read_text(encoding="utf-8")
        for term in ("skill-metadata", "skill-input", "skill-output", "audit-event", "policy-approval-request"):
            self.assertIn(term, content)


if __name__ == "__main__":
    unittest.main()
