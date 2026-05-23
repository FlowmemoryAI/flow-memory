import unittest

from flow_memory.perception import DualStreamPerception
from flow_memory.world_model import PredictiveWorldModel


class WorldModelTests(unittest.TestCase):
    def test_forecast_contains_free_energy_proxy(self) -> None:
        perception = DualStreamPerception().process("Track moving robot")
        prediction = PredictiveWorldModel().forecast(perception)
        self.assertIn("free_energy_proxy", prediction.state)
        self.assertGreater(prediction.confidence, 0)

    def test_forecast_carries_appearance_invariant_motion_signature(self) -> None:
        frames = []
        for x in (0, 1, 2):
            frame = [[0.0 for _ in range(4)] for _ in range(4)]
            frame[1][x] = 1.0
            frames.append(frame)
        perception = DualStreamPerception().process({"frames": frames})

        prediction = PredictiveWorldModel().forecast(perception)

        signature = perception.motion_geometry.spatial_relations[0]["appearance_invariant_signature"]
        self.assertEqual(prediction.state["motion_signature"], signature)
        self.assertTrue(prediction.state["motion_signature"]["appearance_free"])


if __name__ == "__main__":
    unittest.main()
