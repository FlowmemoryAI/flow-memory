import unittest

from flow_memory.skills import SkillManifest


class SkillManifestTests(unittest.TestCase):
    def test_manifest_validates_required_fields(self) -> None:
        with self.assertRaises(ValueError):
            SkillManifest(id="", name="", description="")

    def test_manifest_record_contains_economy_and_risk(self) -> None:
        manifest = SkillManifest(
            id="economic-task",
            name="Economic Task",
            description="task",
            permissions=("marketplace.bid",),
            economic_value=2.0,
            risk_level="high",
        )
        record = manifest.as_record()
        self.assertEqual(record["economic_value"], 2.0)
        self.assertEqual(record["risk_level"], "high")


if __name__ == "__main__":
    unittest.main()
