import unittest

from flow_memory.agents import AgentState


class AgentStateTests(unittest.TestCase):
    def test_state_tracks_events_and_error(self) -> None:
        state = AgentState()
        state.add_event({"event": "created"})
        self.assertEqual(state.recent_events[-1]["event"], "created")
        self.assertTrue(state.as_record()["health"]["ok"])


if __name__ == "__main__":
    unittest.main()
