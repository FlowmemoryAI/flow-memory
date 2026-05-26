import unittest
from typing import cast

from flow_memory.economy.slashing import SlashingEvent


class EconomyV2SlashingTests(unittest.TestCase):
    def test_slashing_event_is_auditable_record(self) -> None:
        event = SlashingEvent(agent_did="did:agent", task_id="task1", reason="failed verification")
        record = event.as_record()
        self.assertLess(cast(float, record["reputation_delta"]), 0)
        self.assertEqual(record["agent_did"], "did:agent")


if __name__ == "__main__":
    unittest.main()
