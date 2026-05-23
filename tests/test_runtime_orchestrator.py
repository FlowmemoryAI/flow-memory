import unittest
from datetime import datetime, timedelta, timezone

from flow_memory.runtime import BaseRuntimeManager, RuntimeEvent, RuntimeOrchestrator


class StepClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 2, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value = current + timedelta(seconds=1)
        return current


def make_orchestrator() -> RuntimeOrchestrator:
    clock = StepClock()
    return RuntimeOrchestrator(
        {
            "memory": BaseRuntimeManager("memory", clock=clock),
            "economy": BaseRuntimeManager("economy", clock=clock),
        },
        clock=clock,
    )


class RuntimeOrchestratorTests(unittest.TestCase):
    def test_orchestrator_registers_and_emits_hash_chained_events(self) -> None:
        orchestrator = make_orchestrator()

        events = orchestrator.events()

        self.assertEqual([event.kind for event in events], ["manager.registered", "manager.registered"])
        self.assertEqual([event.sequence for event in events], [0, 1])
        self.assertEqual(events[0].previous_hash, "GENESIS")
        self.assertEqual(events[1].previous_hash, events[0].event_hash)
        self.assertTrue(orchestrator.verify_events())

    def test_orchestrator_start_tick_status_and_health(self) -> None:
        orchestrator = make_orchestrator()

        started = orchestrator.start_all()
        self.assertEqual(set(started), {"memory", "economy"})
        self.assertTrue(all(status.running for status in started.values()))

        ticked = orchestrator.tick()
        self.assertEqual(ticked["memory"].ticks, 1)
        self.assertEqual(ticked["economy"].ticks, 1)

        statuses = orchestrator.status()
        self.assertTrue(statuses["memory"].running)
        self.assertTrue(statuses["economy"].running)

        health = orchestrator.health()
        self.assertEqual(health.name, "runtime")
        self.assertTrue(health.ok)
        self.assertTrue(health.running)
        self.assertEqual(health.checks, {"memory": True, "economy": True})
        self.assertEqual(health.messages, ())
        self.assertEqual(health.ticks, len(orchestrator.events()))

    def test_orchestrator_routes_events_and_updates_health(self) -> None:
        orchestrator = make_orchestrator()
        orchestrator.start_all()
        event = RuntimeEvent(
            sequence=99,
            kind="runtime.stop",
            manager="memory",
            timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ).with_hash()

        statuses = orchestrator.handle_event(event)

        self.assertEqual(set(statuses), {"memory"})
        self.assertFalse(statuses["memory"].running)
        self.assertEqual(statuses["memory"].handled_events, 1)
        self.assertTrue(orchestrator.status()["economy"].running)
        self.assertFalse(orchestrator.health().ok)
        self.assertEqual(orchestrator.health().messages, ("memory",))
        self.assertEqual(orchestrator.events()[-1].kind, "manager.event_handled")
        self.assertTrue(orchestrator.verify_events())

    def test_orchestrator_is_offline_and_deterministic(self) -> None:
        first = make_orchestrator()
        second = make_orchestrator()

        first.start_all()
        second.start_all()
        first.tick()
        second.tick()
        first.stop("economy")
        second.stop("economy")

        first_events = first.events()
        second_events = second.events()
        self.assertEqual(
            [(event.kind, event.manager, event.payload, event.timestamp) for event in first_events],
            [(event.kind, event.manager, event.payload, event.timestamp) for event in second_events],
        )
        self.assertEqual([event.event_hash for event in first_events], [event.event_hash for event in second_events])
        self.assertTrue(first.verify_events())
        self.assertTrue(second.verify_events())

    def test_orchestrator_rejects_duplicate_or_unknown_managers(self) -> None:
        clock = StepClock()
        orchestrator = RuntimeOrchestrator(clock=clock)
        orchestrator.register("memory", BaseRuntimeManager("memory", clock=clock))

        with self.assertRaises(ValueError):
            orchestrator.register("memory", BaseRuntimeManager("memory", clock=clock))

        with self.assertRaises(KeyError):
            orchestrator.start("missing")


if __name__ == "__main__":
    unittest.main()
