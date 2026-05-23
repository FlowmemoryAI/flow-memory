import unittest

from flow_memory.perception import DualStreamPerception


class StructuredPerceptionTests(unittest.TestCase):
    def test_structured_motion_is_appearance_free(self) -> None:
        observation = {
            "modality": "video",
            "objects": [
                {"id": "cube", "label": "Cube", "color": "red", "positions": [(0, 0), (1, 0), (2, 1)]},
            ],
        }
        perception = DualStreamPerception().process(observation)
        self.assertEqual(perception.entities[0].label, "Cube")
        self.assertIn("appearance_suppression", perception.motion_geometry.invariances)
        self.assertTrue(perception.motion_geometry.trajectories[0]["appearance_free"])
        self.assertNotIn("color", perception.motion_geometry.trajectories[0])
        self.assertGreater(perception.motion_geometry.confidence, 0.5)


if __name__ == "__main__":
    unittest.main()
