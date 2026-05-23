import unittest

from flow_memory.embodiment import LocalGridAdapter, MechanicalNeuralNetwork


class EmbodimentTests(unittest.TestCase):
    def test_local_grid_adapter_moves_with_bounds(self) -> None:
        adapter = LocalGridAdapter(width=2, height=2)
        adapter.reset()
        state = adapter.step({"dx": 5, "dy": 1})
        self.assertEqual(state["position"], (1, 1))

    def test_mechanical_proxy_clamps_stiffness(self) -> None:
        net = MechanicalNeuralNetwork()
        output = net.execute({"beam_a": 1.5, "beam_b": -1})
        self.assertEqual(output["beam_a"], 1.0)
        self.assertEqual(output["beam_b"], 0.0)


if __name__ == "__main__":
    unittest.main()
