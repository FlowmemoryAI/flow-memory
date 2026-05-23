"""Dependency-free runtime managers and local orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, Mapping

from flow_memory.runtime.events import RuntimeEvent, RuntimeHealth, RuntimeStatus, utc_now

Clock = Callable[[], datetime]


@dataclass
class BaseRuntimeManager:
    """Minimal lifecycle surface for local runtime subsystems."""

    name: str
    clock: Clock = utc_now
    _running: bool = field(default=False, init=False, repr=False)
    _started_at: datetime | None = field(default=None, init=False, repr=False)
    _stopped_at: datetime | None = field(default=None, init=False, repr=False)
    _ticks: int = field(default=0, init=False, repr=False)
    _handled_events: int = field(default=0, init=False, repr=False)
    _last_error: str | None = field(default=None, init=False, repr=False)

    def start(self) -> RuntimeStatus:
        if not self._running:
            self._running = True
            self._started_at = self.clock()
            self._stopped_at = None
            self._last_error = None
        return self.status()

    def stop(self) -> RuntimeStatus:
        if self._running:
            self._running = False
            self._stopped_at = self.clock()
        return self.status()

    def status(self) -> RuntimeStatus:
        return RuntimeStatus(
            name=self.name,
            running=self._running,
            ticks=self._ticks,
            handled_events=self._handled_events,
            started_at=self._started_at,
            stopped_at=self._stopped_at,
            last_error=self._last_error,
        )

    def health(self) -> RuntimeHealth:
        return RuntimeHealth.from_status(self.status())

    def tick(self) -> RuntimeStatus:
        if self._running:
            self._ticks += 1
            self._last_error = None
        else:
            self._last_error = "manager is not running"
        return self.status()

    def handle_event(self, event: RuntimeEvent) -> RuntimeStatus:
        self._handled_events += 1
        if event.kind == "runtime.stop" and event.manager in (None, self.name):
            return self.stop()
        if event.kind == "runtime.start" and event.manager in (None, self.name):
            return self.start()
        return self.status()


@dataclass
class RuntimeOrchestrator:
    """Coordinate named managers and keep a deterministic local event chain."""

    managers: Mapping[str, BaseRuntimeManager] | None = None
    clock: Clock = utc_now
    _managers: dict[str, BaseRuntimeManager] = field(default_factory=dict, init=False, repr=False)
    _events: list[RuntimeEvent] = field(default_factory=list, init=False, repr=False)
    _last_hash: str = field(default="GENESIS", init=False, repr=False)

    def __post_init__(self) -> None:
        if self.managers is not None:
            for name, manager in self.managers.items():
                self.register(name, manager)

    def register(self, name: str, manager: BaseRuntimeManager) -> None:
        if not name:
            raise ValueError("runtime manager name must not be empty")
        if name in self._managers:
            raise ValueError(f"runtime manager already registered: {name}")
        if manager.name != name:
            raise ValueError("runtime manager name must match registry name")
        self._managers[name] = manager
        self._emit("manager.registered", name, {"running": manager.status().running})

    def start(self, name: str) -> RuntimeStatus:
        manager = self._manager(name)
        status = manager.start()
        self._emit("manager.started", name, {"running": status.running})
        return status

    def stop(self, name: str) -> RuntimeStatus:
        manager = self._manager(name)
        status = manager.stop()
        self._emit("manager.stopped", name, {"running": status.running})
        return status

    def start_all(self) -> Mapping[str, RuntimeStatus]:
        return {name: self.start(name) for name in self._managers}

    def stop_all(self) -> Mapping[str, RuntimeStatus]:
        return {name: self.stop(name) for name in self._managers}

    def tick(self) -> Mapping[str, RuntimeStatus]:
        statuses: dict[str, RuntimeStatus] = {}
        for name, manager in self._managers.items():
            status = manager.tick()
            statuses[name] = status
            self._emit("manager.tick", name, {"running": status.running, "ticks": status.ticks})
        return statuses

    def handle_event(self, event: RuntimeEvent) -> Mapping[str, RuntimeStatus]:
        targets: Iterable[tuple[str, BaseRuntimeManager]]
        if event.manager is None:
            targets = self._managers.items()
        else:
            targets = ((event.manager, self._manager(event.manager)),)

        statuses: dict[str, RuntimeStatus] = {}
        for name, manager in targets:
            statuses[name] = manager.handle_event(event)
            self._emit("manager.event_handled", name, {"event_kind": event.kind})
        return statuses

    def status(self) -> Mapping[str, RuntimeStatus]:
        return {name: manager.status() for name, manager in self._managers.items()}

    def health(self) -> RuntimeHealth:
        manager_health = {name: manager.health() for name, manager in self._managers.items()}
        checks = {name: health.ok for name, health in manager_health.items()}
        ok = all(checks.values()) if checks else True
        running = all(health.running for health in manager_health.values()) if manager_health else False
        messages = tuple(name for name, healthy in checks.items() if not healthy)
        return RuntimeHealth(name="runtime", ok=ok, running=running, ticks=len(self._events), checks=checks, messages=messages)

    def health_summary(self) -> Mapping[str, object]:
        health = self.health()
        return {"status": "ok" if health.ok else "degraded", "running": health.running, "checks": dict(health.checks)}

    def events(self) -> tuple[RuntimeEvent, ...]:
        return tuple(self._events)

    def verify_events(self) -> bool:
        previous = "GENESIS"
        for event in self._events:
            if event.previous_hash != previous or not event.verifies():
                return False
            previous = event.event_hash
        return True

    def _manager(self, name: str) -> BaseRuntimeManager:
        try:
            return self._managers[name]
        except KeyError as exc:
            raise KeyError(f"unknown runtime manager: {name}") from exc

    def _emit(self, kind: str, manager: str | None, payload: Mapping[str, object] | None = None) -> RuntimeEvent:
        event = RuntimeEvent(
            sequence=len(self._events),
            kind=kind,
            manager=manager,
            payload={} if payload is None else dict(payload),
            timestamp=self.clock(),
            previous_hash=self._last_hash,
        ).with_hash()
        self._events.append(event)
        self._last_hash = event.event_hash
        return event
