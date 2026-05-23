import unittest
from datetime import datetime, timedelta, timezone

from flow_memory.runtime import BaseRuntimeManager, RuntimeEvent, RuntimeHealth, RuntimeStatus


class StepClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value = current + timedelta(seconds=1)
        return current


class RuntimeManagerTests(unittest.TestCase):
    def test_manager_lifecycle_status_and_health(self) -> None:
        clock = StepClock()
        manager = BaseRuntimeManager("memory", clock=clock)

        initial = manager.status()
        self.assertIsInstance(initial, RuntimeStatus)
        self.assertFalse(initial.running)
        self.assertIsNone(initial.started_at)
        self.assertIsInstance(manager.health(), RuntimeHealth)
        self.assertFalse(manager.health().ok)

        started = manager.start()
        self.assertTrue(started.running)
        self.assertEqual(started.started_at, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertTrue(manager.health().ok)

        ticked = manager.tick()
        self.assertTrue(ticked.running)
        self.assertEqual(ticked.ticks, 1)
        self.assertIsNone(ticked.last_error)

        stopped = manager.stop()
        self.assertFalse(stopped.running)
        self.assertEqual(stopped.stopped_at, datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc))
        self.assertFalse(manager.health().ok)

    def test_manager_records_stopped_tick_without_incrementing(self) -> None:
        manager = BaseRuntimeManager("economy", clock=StepClock())

        status = manager.tick()

        self.assertFalse(status.running)
        self.assertEqual(status.ticks, 0)
        self.assertEqual(status.last_error, "manager is not running")
        self.assertEqual(manager.health().messages, ("started", "no_last_error", "running"))

    def test_manager_handle_event_start_stop_and_count(self) -> None:
        clock = StepClock()
        manager = BaseRuntimeManager("perception", clock=clock)

        start_event = RuntimeEvent(sequence=0, kind="runtime.start", manager="perception", timestamp=clock()).with_hash()
        start_status = manager.handle_event(start_event)
        self.assertTrue(start_status.running)
        self.assertEqual(start_status.handled_events, 1)

        ignored = RuntimeEvent(sequence=1, kind="runtime.stop", manager="other", timestamp=clock()).with_hash()
        ignored_status = manager.handle_event(ignored)
        self.assertTrue(ignored_status.running)
        self.assertEqual(ignored_status.handled_events, 2)

        stop_event = RuntimeEvent(sequence=2, kind="runtime.stop", manager=None, timestamp=clock()).with_hash()
        stop_status = manager.handle_event(stop_event)
        self.assertFalse(stop_status.running)
        self.assertEqual(stop_status.handled_events, 3)

    def test_runtime_event_hash_is_deterministic_and_tamper_evident(self) -> None:
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        first = RuntimeEvent(sequence=0, kind="manager.tick", manager="memory", payload={"ticks": 1}, timestamp=timestamp)
        second = RuntimeEvent(sequence=0, kind="manager.tick", manager="memory", payload={"ticks": 1}, timestamp=timestamp)

        hashed = first.with_hash()

        self.assertEqual(hashed.event_hash, second.with_hash().event_hash)
        self.assertTrue(hashed.verifies())
        tampered = RuntimeEvent(
            sequence=hashed.sequence,
            kind=hashed.kind,
            manager=hashed.manager,
            payload={"ticks": 2},
            timestamp=hashed.timestamp,
            previous_hash=hashed.previous_hash,
            event_hash=hashed.event_hash,
        )
        self.assertFalse(tampered.verifies())


if __name__ == "__main__":
    unittest.main()
