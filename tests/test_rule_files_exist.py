import unittest
from pathlib import Path


class RuleFilesExistTests(unittest.TestCase):
    def test_required_rule_files_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        expected = {
            "policy.dl": "approval_required",
            "reputation.dl": "reputation_delta",
            "slashing.dl": "slash_event",
            "task_eligibility.dl": "eligible",
            "memory_consolidation.dl": "consolidate",
        }
        for filename, marker in expected.items():
            content = (root / "rules" / filename).read_text(encoding="utf-8")
            self.assertIn(".decl", content)
            self.assertIn(".output", content)
            self.assertIn(marker, content)


if __name__ == "__main__":
    unittest.main()
