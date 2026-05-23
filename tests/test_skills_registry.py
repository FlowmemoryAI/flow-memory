import unittest

from flow_memory.skills import SkillManifest, SkillRegistry


class SkillRegistryTests(unittest.TestCase):
    def test_register_get_and_list(self) -> None:
        registry = SkillRegistry()
        manifest = SkillManifest(id="brief", name="Brief", description="brief")
        registry.register(manifest)
        self.assertIs(registry.get("brief"), manifest)
        self.assertEqual(tuple(item.skill_id for item in registry.list()), ("brief",))


if __name__ == "__main__":
    unittest.main()
