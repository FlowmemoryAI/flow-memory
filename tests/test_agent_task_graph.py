import unittest

from flow_memory.agents import graph_from_steps


class AgentTaskGraphTests(unittest.TestCase):
    def test_task_graph_dependencies_and_failure_propagation(self) -> None:
        graph = graph_from_steps(("a", "b"))
        first = graph.ready_nodes()[0]
        first.start()
        first.complete()
        second = graph.ready_nodes()[0]
        second.start()
        second.fail()
        graph.propagate_failure(second.node_id)
        self.assertIn(second.status, {"failed", "terminal_failed"})


if __name__ == "__main__":
    unittest.main()
