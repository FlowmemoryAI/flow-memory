import unittest

from flow_memory.perception import DualStreamPerception


class PerceptionTests(unittest.TestCase):
    def test_dorsal_stream_marks_appearance_invariance(self) -> None:
        perception = DualStreamPerception().process("Explore moving objects and report motion")
        self.assertIn("appearance_suppression", perception.motion_geometry.invariances)
        self.assertGreater(perception.motion_geometry.confidence, 0.2)

    def test_video_like_frame_delta_creates_trajectory(self) -> None:
        perception = DualStreamPerception().process(
            {
                "modality": "video",
                "frames": [[[0], [1]], [[1], [2]]],
                "objects": ["agent", "target"],
                "text": "agent moving toward target",
            }
        )
        self.assertGreater(len(perception.motion_geometry.trajectories), 0)
        self.assertTrue(any(t["source"] == "frame_delta_proxy" for t in perception.motion_geometry.trajectories))
        self.assertIn("agent", [entity.label for entity in perception.entities])


if __name__ == "__main__":
    unittest.main()
