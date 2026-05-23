import unittest

from flow_memory.ir import PermissionSpec, SkillSpec
from flow_memory.ir.skill_adapter import skill_manifest_from_ir


class FlowIRSkillAdapterTests(unittest.TestCase):
    def test_skill_maps_to_manifest(self) -> None:
        manifest = skill_manifest_from_ir(SkillSpec(id="s", description="d", permissions=(PermissionSpec("respond"),)))
        self.assertEqual(manifest.id, "s")
        self.assertEqual(manifest.permissions, ("respond",))


if __name__ == "__main__":
    unittest.main()
